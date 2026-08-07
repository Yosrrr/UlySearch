"""
Pipeline complet : scraping -> filtre par date -> déduplication stricte
(100% des champs) -> scoring par catégorie -> enrichissement acheteur
-> assignation -> insertion.

Réutilisable à la fois en CLI (scripts/run_pipeline_all.py) et comme
tâche Celery (app/workers/tasks.py).
"""
import hashlib
from datetime import date, datetime, timedelta

from unidecode import unidecode
from app.core.cache import cache_get, cache_set, cache_delete_pattern
from app.schemas.sotradies import SotradiesRaw
from app.core.database import SessionLocal
from app.core.keywords import CATEGORIES
from app.models.sotradies import Sotradies
from app.services.scrapers.onmp_scraper import OnmpScraper
from app.services.scrapers.appeloffres_scraper import AppeloffresScraper
from app.services.scoring_orchestrator import score_tender_full
from app.services.keyword_classifier import best_category
from app.services.buyer_matcher import match_buyer

SCRAPE_CACHE_TTL = 25 * 60  # 25 min — légèrement sous le cycle de 30 min


def fetch_with_cache(scraper) -> list:
    """Sert un résultat déjà scrapé si disponible en cache (moins de 25 min),
    pour ne jamais solliciter un site plusieurs fois en rafale."""
    cache_key = f"scrape:{scraper.source_name}"
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[cache] {scraper.source_name} : résultat servi depuis le cache "
              f"(aucune requête envoyée au site)")
        return [SotradiesRaw(**item) for item in cached]

    tenders = scraper.fetch_tenders()
    cache_set(cache_key, [t.model_dump(mode="json") for t in tenders], SCRAPE_CACHE_TTL)
    return tenders

def compute_hash(t) -> str:
    """Identifie un marché par son contenu STABLE. date_limite et
    budget_estime sont volontairement exclus : ce sont des champs qui
    peuvent être mis à jour par la source (report de délai, précision
    tardive du budget) sans que ce soit un nouveau marché."""
    parts = [
        t.source,
        t.reference or "",
        unidecode(t.objet or "").lower().strip(),
        unidecode(t.acheteur or "").lower().strip(),
        unidecode(t.categorie or "").lower().strip(),
        str(t.date_publication),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def filter_today_only(tenders: list, target_date: date) -> tuple[list, int]:
    kept, sans_date = [], 0
    for t in tenders:
        if t.date_publication is None:
            sans_date += 1
            continue
        if t.date_publication.date() == target_date:
            kept.append(t)
    return kept, sans_date


def run_pipeline(target_date: date | None = None) -> dict:
    target_date = target_date or (datetime.now().date() - timedelta(days=1))
    print(f"[pipeline] Date ciblée : {target_date.isoformat()}")

    scrapers = [OnmpScraper(), AppeloffresScraper()]
    db = SessionLocal()
    

    total_nouveaux, total_doublons, total_hors_date, total_sans_date = 0, 0, 0, 0
    retenus, non_retenus = [], []
    seen_this_run: set[str] = set()

    for scraper in scrapers:
        print(f"[pipeline] Source : {scraper.source_name}")
        all_tenders = fetch_with_cache(scraper)
        tenders, sans_date = filter_today_only(all_tenders, target_date)
        total_hors_date += (len(all_tenders) - len(tenders) - sans_date)
        total_sans_date += sans_date
        print(f"[pipeline] {scraper.source_name} : {len(tenders)} marché(s) du {target_date.isoformat()}")

        for t in tenders:
            tender_id = compute_hash(t)

            if tender_id in seen_this_run:
                total_doublons += 1
                continue
            seen_this_run.add(tender_id)

            existing = db.query(Sotradies).filter_by(id=tender_id).first()
            if existing:
                total_doublons += 1
                # Le marché existe déjà : on ne touche jamais date_detection
                # (date de première détection), mais on met à jour les champs
                # qui peuvent légitimement évoluer d'une source à l'autre.
                changed = False
                if existing.date_limite != t.date_limite:
                    existing.date_limite = t.date_limite
                    changed = True
                if existing.budget_estime != t.budget_estime:
                    existing.budget_estime = t.budget_estime
                    changed = True
                if changed:
                    existing.date_derniere_action = datetime.utcnow()
                    print(f"[pipeline] Marché mis à jour (date/budget modifié) : {t.objet[:60]}")
                continue

            total_nouveaux += 1
            score_details = score_tender_full(t)
            categorie, score = best_category(score_details)
            commercial = CATEGORIES[categorie]["commercial"] if categorie else None
            acheteur_connu = match_buyer(t.acheteur)

            record = Sotradies(
                id=tender_id,
                reference=t.reference,
                objet=t.objet,
                acheteur=t.acheteur,
                categorie=t.categorie,
                date_publication=t.date_publication,
                date_limite=t.date_limite,
                budget_estime=t.budget_estime,
                source=t.source,
                lien=t.lien,
                statut="nouveau",
                commercial_assigne=commercial,
                score_details=score_details,
                acheteur_connu=acheteur_connu,
            )
            db.add(record)

            entry = (score, categorie, commercial, t.source, t.objet, acheteur_connu)
            (retenus if score > 0 else non_retenus).append(entry)

    db.commit()
    db.close()
    cache_delete_pattern("tenders:list:*")

    retenus.sort(key=lambda e: e[0], reverse=True)

    print(f"\n{'='*90}")
    print(f"RETENUS ({len(retenus)}) — triés par score décroissant")
    print(f"{'='*90}")
    for score, cat, com, source, objet, acheteur_connu in retenus:
        marqueur = " 🔴 ALERTE INSTANTANÉE" if score > 80 else ""
        badge = " ⭐ CLIENT CONNU" if acheteur_connu == "Oui" else ""
        print(f"[{score}% | {cat} | {com or 'NON ASSIGNÉ'} | {source}]{marqueur}{badge} {objet[:60]}")

    summary = {
        "date_ciblee": target_date.isoformat(),
        "nouveaux": total_nouveaux,
        "doublons": total_doublons,
        "hors_date": total_hors_date,
        "sans_date": total_sans_date,
        "retenus": len(retenus),
        "alertes_instantanees": sum(1 for score, *_ in retenus if score > 80),
        "acheteurs_connus": sum(1 for *_, ac in retenus if ac == "Oui"),
        "non_retenus": len(non_retenus),
    }

    print(f"\n[pipeline] Résumé : {summary}")
    return summary