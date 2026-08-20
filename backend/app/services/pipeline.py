"""
Pipeline complet : scraping -> filtre par date -> déduplication stricte
(100% des champs) -> scoring par catégorie -> enrichissement acheteur
-> assignation -> insertion.

Réutilisable à la fois en CLI (scripts/run_pipeline_all.py) et comme
tâche Celery (app/workers/tasks.py).
"""
import hashlib
from datetime import date, datetime

from unidecode import unidecode

from app.services.mailer import send_email
from app.core.config import settings
from app.core.cache import cache_get, cache_set, cache_delete_pattern
from app.schemas.sotradies import SotradiesRaw
from app.core.database import session_scope
from app.core.keywords import CATEGORIES, EXCLUSION_KEYWORDS
from app.models.sotradies import Sotradies
from app.services.scrapers.onmp_scraper import OnmpScraper
from app.services.scrapers.appeloffres_scraper import AppeloffresScraper
from app.services.buyer_matcher import match_buyer
from app.services.config_service import get_or_create_config
from app.services.detail_fetcher import fetch_detail_text
from app.services.raw_dump import dump_tender_to_txt
from app.services.ai_filter_and_extract import filter_and_extract, _EMPTY_RESULT as _EMPTY_RESULT_FILTER

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


def _alert_scraper_failure(source_name: str) -> None:
    """0 résultat brut d'un scraper est anormal — alerte immédiate,
    pour ne jamais découvrir un site cassé en silence."""
    print(f"[pipeline] ⚠️ ALERTE : {source_name} n'a retourné aucun marché — site possiblement cassé.")
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            f"⚠️ Scraper {source_name} : 0 résultat — vérification nécessaire",
            f"""<p>Le scraper <b>{source_name}</b> n'a retourné <b>aucun marché</b> lors du dernier passage.</p>
                <p>Causes possibles : structure du site modifiée, site temporairement inaccessible,
                blocage IP/captcha, identifiants expirés.</p>
                <p>Vérifiez manuellement le site, et si besoin le dossier <code>debug_{source_name}/</code>
                (capture d'écran + HTML brut sauvegardés automatiquement en cas d'échec).</p>""",
        )
    except Exception as e:
        print(f"[pipeline] Échec de l'envoi de l'alerte technique : {e}")


def run_pipeline(target_date: date | None = None) -> dict:
    target_date = target_date or datetime.now().date()
    print(f"[pipeline] Date ciblée : {target_date.isoformat()}")

    scrapers = [OnmpScraper(), AppeloffresScraper()]

    total_nouveaux, total_doublons, total_hors_date, total_sans_date = 0, 0, 0, 0
    retenus, non_retenus = [], []
    seen_this_run: set[str] = set()
    seuil_alerte = settings.RELEVANCE_INSTANT_ALERT_THRESHOLD  # valeur de repli si jamais le with échoue avant assignation

    with session_scope() as db:
        config = get_or_create_config(db)
        seuil_retention = config.score_decision_threshold
        seuil_alerte = config.score_instant_alert_threshold  # ⬅️ lu depuis la config admin, plus depuis .env

        for scraper in scrapers:
            print(f"[pipeline] Source : {scraper.source_name}")
            all_tenders = fetch_with_cache(scraper)

            if len(all_tenders) == 0:
                _alert_scraper_failure(scraper.source_name)

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

                text_check = unidecode(t.objet or "").lower()
                if any(unidecode(kw).lower() in text_check for kw in EXCLUSION_KEYWORDS):
                    categorie, score = None, 0
                    ai_result = dict(_EMPTY_RESULT_FILTER)
                    ai_result["raison"] = "Exclu par mot-clé, avant appel IA"
                else:
                    detail_text = fetch_detail_text(t.source, t.lien)
                    dump_path = dump_tender_to_txt(tender_id, t, detail_text)
                    ai_result = filter_and_extract(dump_path.read_text(encoding="utf-8"))
                    categorie = ai_result["categorie"] if ai_result["pertinent"] else None
                    score = ai_result["score"] if ai_result["pertinent"] else 0

                score_details = {cat: {"score": 0, "mots_cles_matches": [], "methode": "ia_directe"} for cat in CATEGORIES}
                if categorie:
                    score_details[categorie] = {
                        "score": score,
                        "mots_cles_matches": [],
                        "methode": "ia_directe",
                        "raison_ia": ai_result.get("raison", ""),
                    }

                commercial = CATEGORIES[categorie]["commercial"] if categorie else None
                acheteur_connu = match_buyer(t.acheteur)
                detail_info = {
                    "description_detaillee": ai_result.get("description_detaillee"),
                    "budget_detecte": ai_result.get("budget_detecte"),
                    "duree_execution": ai_result.get("duree_execution"),
                    "montant_cautionnement": ai_result.get("montant_cautionnement"),
                    "type_marche": ai_result.get("type_marche"),
                    "procedure_passation": ai_result.get("procedure_passation"),
                    "region_execution": ai_result.get("region_execution"),
                    "date_debut_execution": ai_result.get("date_debut_execution"),
                    "date_ouverture_offres": ai_result.get("date_ouverture_offres"),
                    "lieu_ouverture_offres": ai_result.get("lieu_ouverture_offres"),
                    "caractere_prix": ai_result.get("caractere_prix"),
                }

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
                    description_detaillee=detail_info["description_detaillee"],
                    budget_detecte=detail_info["budget_detecte"],
                    duree_execution=detail_info["duree_execution"],
                    montant_cautionnement=detail_info.get("montant_cautionnement"),
                    type_marche=detail_info.get("type_marche"),
                    procedure_passation=detail_info.get("procedure_passation"),
                    region_execution=detail_info.get("region_execution"),
                    date_debut_execution=detail_info.get("date_debut_execution"),
                    date_ouverture_offres=detail_info.get("date_ouverture_offres"),
                    lieu_ouverture_offres=detail_info.get("lieu_ouverture_offres"),
                    caractere_prix=detail_info.get("caractere_prix"),
                )
                db.add(record)

                if score >= seuil_retention:
                    record.statut = "retenu"
                entry = (score, categorie, commercial, t.source, t.objet, acheteur_connu)
                (retenus if score >= seuil_retention else non_retenus).append(entry)
    # session_scope() a déjà fait le commit ici — plus de db.commit()/db.close() manuels

    cache_delete_pattern("tenders:list:*")

    retenus.sort(key=lambda e: e[0], reverse=True)

    print(f"\n{'='*90}")
    print(f"RETENUS ({len(retenus)}) — triés par score décroissant")
    print(f"{'='*90}")
    for score, cat, com, source, objet, acheteur_connu in retenus:
        marqueur = " 🔴 ALERTE INSTANTANÉE" if score > seuil_alerte else ""
        badge = " ⭐ CLIENT CONNU" if acheteur_connu == "Oui" else ""
        print(f"[{score}% | {cat} | {com or 'NON ASSIGNÉ'} | {source}]{marqueur}{badge} {objet[:60]}")

    summary = {
        "date_ciblee": target_date.isoformat(),
        "nouveaux": total_nouveaux,
        "doublons": total_doublons,
        "hors_date": total_hors_date,
        "sans_date": total_sans_date,
        "retenus": len(retenus),
        "alertes_instantanees": sum(1 for score, *_ in retenus if score > seuil_alerte),
        "acheteurs_connus": sum(1 for *_, ac in retenus if ac == "Oui"),
        "non_retenus": len(non_retenus),
    }

    print(f"\n[pipeline] Résumé : {summary}")
    return summary