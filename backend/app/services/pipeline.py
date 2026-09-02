"""
Pipeline complet : scraping -> filtre par date -> déduplication stricte
(100% des champs stables) -> scoring RÈGLES d'abord (mots-clés positifs,
IA locale uniquement en arbitrage des cas ambigus — Principe 1 du CdC)
-> extraction de détail IA UNIQUEMENT pour les marchés retenus
-> enrichissement acheteur -> assignation -> insertion.

Réutilisable à la fois en CLI (scripts/run_pipeline_all.py) et comme
tâche Celery (app/workers/tasks.py).

⚠️ Configuration métier (catégories, mots-clés, exclusions, règles
d'assignation, seuils, sources actives) lue exclusivement depuis la
table `configuration` (exigence §6.5 du cahier des charges).

⚠️ Architecture de scoring (retour au Principe 1, remplace la décision
"IA directe" du 17/08 qui produisait des faux négatifs massifs avec le
modèle local 3B) :
  Tier 1 : mots-clés positifs par catégorie (déterministe, 0 coût)
  Tier 2 : IA locale seulement si aucun match exact mais ressemblance
           floue (needs_ai_fallback)
  Extraction IA (budget, dates, procédure...) : uniquement sur les
  marchés déjà retenus — elle ENRICHIT, ne dégrade jamais le verdict.
"""
import hashlib
from datetime import date, datetime, UTC
from uuid import uuid4
import time


from unidecode import unidecode

from app.services.mailer import send_email
from app.core.config import settings
from app.core.cache import cache_get, cache_set, cache_delete_pattern
from app.schemas.sotradies import SotradiesRaw
from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.services.scrapers.onmp_scraper import OnmpScraper
from app.services.scrapers.tuneps_scraper import TunepsScraper
from app.services.scrapers.appeloffres_scraper import AppeloffresScraper
from app.services.buyer_matcher import match_buyer
from app.services.config_service import get_or_create_config
from app.services.detail_fetcher import fetch_detail_text
from app.services.raw_dump import dump_tender_to_txt
from app.services.scoring_orchestrator import score_tender_full
from app.services.ai_filter_and_extract import (
    filter_and_extract,
    _EMPTY_RESULT as _EMPTY_RESULT_FILTER,
)
from app.services.pipeline_logger import log_pipeline_event

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
    """0 résultat brut d'un scraper est anormal — alerte immédiate."""
    print(f"[pipeline] ⚠️ ALERTE : {source_name} n'a retourné aucun marché — site possiblement cassé.")
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            f"⚠️ Scraper {source_name} : 0 résultat — vérification nécessaire",
            f"""<p>Le scraper <b>{source_name}</b> n'a retourné <b>aucun marché</b> lors du dernier passage.</p>
                <p>Causes possibles : structure du site modifiée, site temporairement inaccessible,
                blocage IP/captcha, identifiants expirés.</p>
                <p>Vérifiez manuellement le site.</p>""",
        )
    except Exception as e:
        print(f"[pipeline] Échec de l'envoi de l'alerte technique : {e}")


def _alert_empty_configuration() -> None:
    """Configuration sans aucune catégorie = pipeline aveugle."""
    print("[pipeline] ⚠️ ALERTE : aucune catégorie configurée en base.")
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            "⚠️ Configuration vide : aucune catégorie définie",
            """<p>Le pipeline de veille s'est exécuté mais <b>aucune catégorie
               n'est configurée</b> dans la table de configuration.</p>
               <p>Action requise : renseigner les catégories dans l'administration.</p>""",
        )
    except Exception as e:
        print(f"[pipeline] Échec de l'envoi de l'alerte configuration : {e}")


def _source_is_active(active_sources: dict, source_name: str) -> bool:
    """Résout les noms actuels des scrapers ET les anciennes clés de config."""
    if not active_sources:
        return True
    aliases = {
        "onmp": ("onmp", "observatoire_national"),
        "appeloffres": ("appeloffres", "tunisie_appel_offre"),
        "tuneps": ("tuneps", "tuneps.tn"),
    }
    keys = aliases.get(source_name, (source_name,))
    configured = next((active_sources[key] for key in keys if key in active_sources), None)
    return configured is None or bool(configured.get("actif", True))


def _best_category(score_details: dict) -> tuple[str | None, int]:
    """Retourne (catégorie, score) du meilleur score dans score_details."""
    best_cat, best_score = None, 0
    for cat, detail in (score_details or {}).items():
        s = int(detail.get("score", 0) or 0)
        if s > best_score:
            best_cat, best_score = cat, s
    return best_cat, best_score


def run_pipeline(target_date: date | None = None) -> dict:
    run_id = uuid4().hex
    target_date = target_date or datetime.now().date()
    print(f"[pipeline] Run ID : {run_id}")
    print(f"[pipeline] Date ciblée : {target_date.isoformat()}")

    scrapers = [OnmpScraper(), AppeloffresScraper(), TunepsScraper()]

    total_nouveaux, total_doublons, total_hors_date, total_sans_date = 0, 0, 0, 0
    ai_errors = 0  # échecs techniques IA (extraction) — pour l'alerte anti-silence
    retenus, non_retenus = [], []
    seen_this_run: set[str] = set()
    seuil_alerte = settings.RELEVANCE_INSTANT_ALERT_THRESHOLD

    with session_scope() as db:
        config = get_or_create_config(db)
        seuil_retention = config.score_decision_threshold
        seuil_alerte = config.score_instant_alert_threshold
        configured_categories = config.categories or {}
        configured_exclusions = [
            kw for kw in (config.exclusion_keywords or []) if str(kw).strip()
        ]
        assignment_rules = config.assignment_rules or {}
        active_sources = config.active_sources or {}

        log_pipeline_event(
            db, run_id, "RUN_STARTED",
            message="Démarrage du pipeline",
            payload={
                "target_date": target_date.isoformat(),
                "seuil_retention": seuil_retention,
                "seuil_alerte": seuil_alerte,
                "categories": list(configured_categories.keys()),
                "active_sources": active_sources,
            },
        )

        if not configured_categories:
            _alert_empty_configuration()
            log_pipeline_event(
                db, run_id, "CONFIG_EMPTY",
                message="Aucune catégorie configurée",
            )

        for scraper in scrapers:
            source_name = scraper.source_name

            if not _source_is_active(active_sources, source_name):
                print(f"[pipeline] Source désactivée par configuration : {source_name}")
                log_pipeline_event(
                    db, run_id, "SOURCE_DISABLED",
                    source=source_name,
                    message="Source désactivée par configuration admin",
                )
                continue

            print(f"[pipeline] Source : {source_name}")
            log_pipeline_event(
                db, run_id, "SCRAPE_STARTED",
                source=source_name,
                message="Début scraping source",
            )

            try:
                all_tenders = fetch_with_cache(scraper)
            except Exception as exc:
                print(f"[pipeline] ❌ Erreur scraper {source_name}: {exc}")
                log_pipeline_event(
                    db, run_id, "SCRAPER_ERROR",
                    source=source_name,
                    message=f"Erreur scraper {source_name}",
                    payload={"error": str(exc)},
                )
                _alert_scraper_failure(source_name)
                continue

            log_pipeline_event(
                db, run_id, "SCRAPE_FINISHED",
                source=source_name,
                message="Fin scraping source",
                payload={"raw_count": len(all_tenders)},
            )

            if len(all_tenders) == 0:
                _alert_scraper_failure(source_name)
                log_pipeline_event(
                    db, run_id, "SCRAPER_EMPTY",
                    source=source_name,
                    message="Scraper a retourné 0 marché",
                )

            tenders, sans_date = filter_today_only(all_tenders, target_date)
            hors_date = len(all_tenders) - len(tenders) - sans_date
            total_hors_date += hors_date
            total_sans_date += sans_date

            log_pipeline_event(
                db, run_id, "FILTER_DATE_SUMMARY",
                source=source_name,
                message="Résumé filtrage date",
                payload={
                    "target_date": target_date.isoformat(),
                    "raw_count": len(all_tenders),
                    "kept_count": len(tenders),
                    "hors_date": hors_date,
                    "sans_date": sans_date,
                },
            )

            print(f"[pipeline] {source_name} : {len(tenders)} marché(s) du {target_date.isoformat()}")

            for t in tenders:
                tender_id = compute_hash(t)

                if tender_id in seen_this_run:
                    total_doublons += 1
                    log_pipeline_event(
                        db, run_id, "DUPLICATE_RUN",
                        source=t.source, tender_id=tender_id,
                        message="Doublon détecté dans le même run",
                        payload={"objet": t.objet, "reference": t.reference},
                    )
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
                        existing.date_derniere_action = datetime.now(UTC).replace(tzinfo=None)
                        print(f"[pipeline] Marché mis à jour (date/budget modifié) : {t.objet[:60]}")
                        log_pipeline_event(
                            db, run_id, "UPDATED_EXISTING",
                            source=t.source, tender_id=tender_id,
                            message="Marché existant mis à jour",
                            payload={
                                "objet": t.objet,
                                "date_limite": t.date_limite.isoformat() if t.date_limite else None,
                            },
                        )
                    else:
                        log_pipeline_event(
                            db, run_id, "DUPLICATE_DB",
                            source=t.source, tender_id=tender_id,
                            message="Doublon déjà présent en base",
                            payload={"objet": t.objet, "reference": t.reference},
                        )
                    continue

                total_nouveaux += 1

                # ----------------------------------------------------------
                # Exclusion par mots-clés négatifs (config admin)
                # ----------------------------------------------------------
                text_check = unidecode(t.objet or "").lower()
                matched_exclusion = next(
                    (kw for kw in configured_exclusions
                     if unidecode(kw).lower() in text_check),
                    None,
                )

                ai_result = dict(_EMPTY_RESULT_FILTER)

                if matched_exclusion:
                    categorie, score = None, 0
                    score_details = {
                        cat: {"score": 0, "mots_cles_matches": [], "methode": "exclusion"}
                        for cat in configured_categories
                    }
                    log_pipeline_event(
                        db, run_id, "EXCLUDED_KEYWORD",
                        source=t.source, tender_id=tender_id,
                        message="Marché exclu par mot-clé négatif",
                        payload={"objet": t.objet, "keyword": matched_exclusion},
                    )
                else:
                    # ------------------------------------------------------
                    # SCORING — Tier 1 : règles (mots-clés positifs)
                    # Tier 2 : IA locale si ambigu
                    # ------------------------------------------------------
                    score_details = score_tender_full(
                        t, configured_categories, configured_exclusions
                    )
                    
                    categorie, score = _best_category(score_details)
                    # Anti-silence : échec technique IA au scoring fallback
                    scoring_ai_failed = any(
                        d.get("raison_ia") == "Erreur technique IA (locale)"
                        for d in score_details.values()
                    )
                    if scoring_ai_failed:
                        ai_errors += 1
                        log_pipeline_event(
                            db, run_id, "AI_ERROR",
                            source=t.source, tender_id=tender_id,
                            message="Échec technique IA au scoring — "
                                    "marché rejeté par défaut (à revérifier)",
                            payload={"objet": t.objet},
                        )

                    log_pipeline_event(
                        db, run_id, "SCORED",
                        source=t.source, tender_id=tender_id,
                        message="Scoring règles/IA-fallback",
                        payload={
                            "categorie": categorie,
                            "score": score,
                            "methodes": {
                                c: d.get("methode")
                                for c, d in score_details.items()
                                if d.get("score", 0) > 0
                            },
                        },
                    )

                    # ------------------------------------------------------
                    # EXTRACTION IA — uniquement pour les marchés retenus
                    # ------------------------------------------------------
                    if score >= seuil_retention:
                        time.sleep(2)  # Pause pour ne pas surcharger le LLM local
                        
                        detail_text = fetch_detail_text(t.source, t.lien)
                        dump_path = dump_tender_to_txt(tender_id, t, detail_text)

                        log_pipeline_event(
                            db, run_id, "DETAIL_FETCHED",
                            source=t.source, tender_id=tender_id,
                            message="Détail récupéré et dump texte créé",
                            payload={
                                "lien": t.lien,
                                "dump_path": str(dump_path),
                                "detail_length": len(detail_text or ""),
                            },
                        )

                        extraction = filter_and_extract(
                            dump_path.read_text(encoding="utf-8"),
                            configured_categories,
                        )

                        if extraction.get("raison") == "Erreur technique IA (locale)":
                            ai_errors += 1

                            # Même en cas d'erreur IA, filter_and_extract peut avoir généré
                             # une description minimale depuis les métadonnées. On la conserve.
                            if extraction.get("description_detaillee"):
                                ai_result["description_detaillee"] = extraction["description_detaillee"]

                            log_pipeline_event(
                                db,
                                run_id,
                                "AI_ERROR",
                                source=t.source,
                                tender_id=tender_id,
                                message="Échec technique IA extraction — description fallback conservée",
                                payload={"objet": t.objet},
                            )
                        else:
                            ai_result = {
                                **ai_result,
                                **{k: v for k, v in extraction.items() if v not in (None, "", [])},
                            }

                            log_pipeline_event(
                                db,
                                run_id,
                                "AI_RESULT",
                                source=t.source,
                                tender_id=tender_id,
                                message="Extraction IA de détail (enrichissement)",
                                payload={
                                    "pertinent": extraction.get("pertinent"),
                                    "categorie_ia": extraction.get("categorie"),
                                    "score_ia": extraction.get("score"),
                                    "raison": extraction.get("raison"),
                                },
                            )
                # Assignation
                commercial = None
                if categorie and categorie in configured_categories:
                    commercial = next(iter(assignment_rules.get(categorie, [])), None)
                    commercial = commercial or configured_categories[categorie].get("commercial")

                log_pipeline_event(
                    db, run_id, "ASSIGNED",
                    source=t.source, tender_id=tender_id,
                    message="Assignation commerciale calculée",
                    payload={
                        "categorie": categorie,
                        "commercial": commercial,
                        "assignment_rule": assignment_rules.get(categorie) if categorie else None,
                    },
                )

                acheteur_connu = match_buyer(t.acheteur) or "Inconnu"

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
                    description_detaillee=ai_result.get("description_detaillee"),
                    budget_detecte=ai_result.get("budget_detecte"),
                    duree_execution=ai_result.get("duree_execution"),
                    montant_cautionnement=ai_result.get("montant_cautionnement"),
                    type_marche=ai_result.get("type_marche"),
                    procedure_passation=ai_result.get("procedure_passation"),
                    region_execution=ai_result.get("region_execution"),
                    date_debut_execution=ai_result.get("date_debut_execution"),
                    date_ouverture_offres=ai_result.get("date_ouverture_offres"),
                    lieu_ouverture_offres=ai_result.get("lieu_ouverture_offres"),
                    caractere_prix=ai_result.get("caractere_prix"),
                )
                db.add(record)

                if score >= seuil_retention:
                    record.statut = "retenu"

                log_pipeline_event(
                    db, run_id, "INSERTED",
                    source=t.source, tender_id=tender_id,
                    message="Marché inséré en base",
                    payload={
                        "objet": t.objet,
                        "score": score,
                        "categorie": categorie,
                        "commercial": commercial,
                        "statut": record.statut,
                        "acheteur_connu": acheteur_connu,
                    },
                )

                log_pipeline_event(
                    db, run_id,
                    "RETAINED" if score >= seuil_retention else "REJECTED",
                    source=t.source, tender_id=tender_id,
                    message="Marché retenu" if score >= seuil_retention else "Marché non retenu",
                    payload={"score": score, "seuil_retention": seuil_retention},
                )

                entry = (score, categorie, commercial, t.source, t.objet, acheteur_connu)
                (retenus if score >= seuil_retention else non_retenus).append(entry)

        # Anti-silence : si des échecs IA techniques ont eu lieu, alerte admin.
        if ai_errors:
            print(f"[pipeline] ⚠️ {ai_errors} échec(s) technique(s) IA pendant ce run.")
            try:
                send_email(
                    settings.ADMIN_ALERT_EMAIL,
                    f"⚠️ Pipeline : {ai_errors} échec(s) IA locale",
                    f"""<p>Le pipeline (run <code>{run_id}</code>) a rencontré
                        <b>{ai_errors}</b> échec(s) technique(s) du modèle IA local
                        lors de l'extraction de détail.</p>
                        <p>Les marchés concernés restent retenus (verdict des règles),
                        mais leurs champs enrichis (budget, procédure...) sont vides.</p>
                        <p>Vérifiez qu'Ollama est démarré et que le modèle
                        <code>{settings.OLLAMA_MODEL}</code> est disponible.</p>""",
                )
            except Exception as e:
                print(f"[pipeline] Échec envoi alerte IA : {e}")

        log_pipeline_event(
            db, run_id, "RUN_FINISHED",
            message="Fin du pipeline",
            payload={
                "target_date": target_date.isoformat(),
                "nouveaux": total_nouveaux,
                "doublons": total_doublons,
                "hors_date": total_hors_date,
                "sans_date": total_sans_date,
                "retenus": len(retenus),
                "non_retenus": len(non_retenus),
                "ai_errors": ai_errors,
            },
        )

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
        "run_id": run_id,
        "date_ciblee": target_date.isoformat(),
        "nouveaux": total_nouveaux,
        "doublons": total_doublons,
        "hors_date": total_hors_date,
        "sans_date": total_sans_date,
        "retenus": len(retenus),
        "alertes_instantanees": sum(1 for score, *_ in retenus if score > seuil_alerte),
        "acheteurs_connus": sum(1 for *_, ac in retenus if ac == "Oui"),
        "non_retenus": len(non_retenus),
        "ai_errors": ai_errors,
    }

    print(f"\n[pipeline] Résumé : {summary}")
    return summary