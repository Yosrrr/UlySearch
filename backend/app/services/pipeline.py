"""
Pipeline complet :

Phase 1 — Collecte globale (NEUTRE, exécutée une seule fois par offre).
Phase 2 — Scoring par client (exécutée une fois par entreprise abonnée).
Phase 3 — Enrichissement IA (déclenché UNE SEULE FOIS par offre).
"""
from __future__ import annotations

import hashlib
import html
import time
from datetime import UTC, date, datetime
from uuid import uuid4
from decimal import Decimal

from sqlalchemy import func, select
from unidecode import unidecode

from app.core.cache import cache_delete_pattern, cache_get, cache_set
from app.core.config import settings
from app.core.database import session_scope

from app.models.commercial import Commercial
from app.models.company_source import CompanySource
from app.models.source_account import SourceAccount
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.scraping_source import ScrapingSource
from app.models.sotradies import Sotradies
from app.models.pipeline_log import PipelineLog

from app.schemas.sotradies import SotradiesRaw

from app.services.ai_filter_and_extract import (
    _EMPTY_RESULT as _EMPTY_RESULT_FILTER,
    filter_and_extract,
)
from app.services.buyer_matcher import match_buyer
from app.services.detail_fetcher import fetch_detail_text
from app.services.mailer import send_email
from app.services.pipeline_logger import log_pipeline_event
from app.services.raw_dump import dump_tender_to_txt
from app.services.scoring_orchestrator import score_tender_full
from app.services.keyword_classifier import first_matching_keyword

from app.services.scrapers.onmp_scraper import OnmpScraper
from app.services.scrapers.tuneps_scraper import TunepsScraper
from app.services.scrapers.universal_scraper import UniversalScraper
from app.services.source_credentials import decrypt_source_password

SCRAPE_CACHE_TTL = 25 * 60

def _reset_ai_cache() -> None:
    """Vide le cache IA entre deux runs (évite les fuites mémoire)."""
    try:
        from app.services.scoring_orchestrator import _AI_CALL_CACHE
        _AI_CALL_CACHE.clear()
    except Exception:
        pass
def _build_scrapers(company_id: int | None = None) -> list:
    """
    Charge les sources actives.
    Si company_id est fourni, ne charge que les sources de CE client.
    """
    with session_scope() as db:
        query = (
            select(
                ScrapingSource.id,
                ScrapingSource.nom,
                ScrapingSource.type,
                ScrapingSource.url,
                ScrapingSource.use_browser,
                ScrapingSource.max_pages,
                CompanySource.id.label("company_source_id"),
                SourceAccount.login,
                SourceAccount.password_encrypted,
            )
            .join(CompanySource, CompanySource.source_id == ScrapingSource.id)
            .outerjoin(SourceAccount, SourceAccount.company_source_id == CompanySource.id)
            .where(
                ScrapingSource.actif.is_(True),
                CompanySource.actif.is_(True),
            )
            .distinct()
            .order_by(ScrapingSource.id)
        )

        # Filtre optionnel par client (run immédiat après inscription)
        if company_id is not None:
            query = query.where(CompanySource.company_id == company_id)

        source_specs = [
            dict(row)
            for row in db.execute(query).mappings().all()
        ]

    dedicated_factories = {
        "onmp": OnmpScraper,
        "tuneps": TunepsScraper,
        
    }

    scrapers = []
    for source in source_specs:
        source_type = str(source["type"] or "").strip().lower()
        source_name_lower = str(source["nom"] or "").strip().lower()
        auth = None
        if source.get("login") and source.get("password_encrypted"):
            auth = (
                source["login"],
                decrypt_source_password(source["password_encrypted"]),
            )

        if source_type == "dedie":
            factory = dedicated_factories.get(source_name_lower)
            if factory is None:
                print(f"[pipeline] Connecteur inconnu : {source['nom']}")
                continue
            scraper = factory(auth=auth)

        elif source_type == "universel":
            url = str(source["url"] or "").strip()
            if not url:
                print(f"[pipeline] Source {source['id']} sans URL : ignorée")
                continue
            scraper = UniversalScraper(
                source_name=f"web_{source['id']}",
                url=url,
                use_browser=bool(source["use_browser"]),
                max_pages=int(source["max_pages"] or 3),
                auth=auth,
            )
        else:
            print(f"[pipeline] Type inconnu : {source['type']}")
            continue

        scraper.company_id = company_id
        scrapers.append(scraper)
        print(f"[pipeline] Source : {source['nom']} | {getattr(scraper, 'source_name', '')}")

    return scrapers


def fetch_with_cache(scraper) -> list[SotradiesRaw]:
    source_name = getattr(scraper, "source_name", scraper.__class__.__name__)
    cache_key = f"scrape:{getattr(scraper, 'company_id', 'global')}:{source_name}"
    cached = cache_get(cache_key)

    if cached is not None:
        return [
            item if isinstance(item, SotradiesRaw) else SotradiesRaw(**item)
            for item in cached
        ]

    raw = scraper.fetch_tenders() or []
    if not isinstance(raw, list):
        raw = list(raw)

    tenders: list[SotradiesRaw] = []
    for item in raw:
        if isinstance(item, SotradiesRaw):
            tenders.append(item)
        elif isinstance(item, dict):
            tenders.append(SotradiesRaw(**item))
        elif hasattr(item, "model_dump"):
            tenders.append(SotradiesRaw(**item.model_dump()))

    cache_set(cache_key, [t.model_dump(mode="json") for t in tenders], SCRAPE_CACHE_TTL)
    return tenders


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(unidecode(str(value)).lower().strip().split())


def compute_hash(tender: SotradiesRaw, fallback_source: str | None = None) -> str:
    parts = [
        _normalize(tender.reference),
        _normalize(tender.objet),
        _normalize(tender.acheteur),
        str(tender.date_publication or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def filter_today_only(
    tenders: list[SotradiesRaw],
    target_date: date,
) -> tuple[list[SotradiesRaw], int]:
    """
    Garde les offres pertinentes pour ce run :
    - publiées aujourd'hui (nouvelles du jour)
    - OU sans date de publication mais avec date limite future
      (TUNEPS renvoie souvent des offres publiées il y a plusieurs jours
       mais encore ouvertes — on ne veut pas les perdre)

    Retourne (offres_gardées, nb_sans_aucune_date).
    """
    kept: list[SotradiesRaw] = []
    sans_date = 0
    now = datetime.now()

    for t in tenders:
        pub = getattr(t, "date_publication", None)
        lim = getattr(t, "date_limite", None)

        # Convertir en date si datetime
        pub_date = pub.date() if isinstance(pub, datetime) else pub
        lim_date = lim.date() if isinstance(lim, datetime) else lim

        # Cas 1 : publiée aujourd'hui → toujours garder
        if pub_date == target_date:
            kept.append(t)
            continue

        # Cas 2 : publiée avant aujourd'hui, date limite future → garder
        if pub_date is not None and pub_date < target_date:
            if lim_date is not None and lim_date >= target_date:
                kept.append(t)
                continue
            # Publiée avant, date limite passée ou absente → ignorer
            continue

        # Cas 3 : pas de date de publication, date limite future → garder
        if pub_date is None and lim_date is not None and lim_date >= target_date:
            kept.append(t)
            continue

        # Cas 4 : aucune date exploitable
        if pub_date is None and lim_date is None:
            sans_date += 1
            continue

    return kept, sans_date


def _source_is_active(active_sources: dict, source_name: str) -> bool:
    """Compatibilité pour les anciennes configurations de sources.

    Le pipeline actuel utilise les abonnements ``CompanySource`` comme
    source de vérité, mais ce helper reste utile aux scripts et validations
    qui lisent encore ``Configuration.active_sources``.
    """
    if not active_sources:
        return True

    normalized = str(source_name or "").strip().lower()
    if normalized.startswith("web_"):
        return True

    aliases = {
        "onmp": ("onmp", "observatoire_national"),
        "tuneps": ("tuneps", "tuneps.tn"),
    }
    keys = aliases.get(normalized, (normalized,))
    normalized_config = {
        str(key).strip().lower(): value
        for key, value in active_sources.items()
    }

    configured = next(
        (normalized_config[key] for key in keys if key in normalized_config),
        None,
    )
    if configured is None:
        return True
    if isinstance(configured, dict):
        return bool(configured.get("actif", True))
    return bool(configured)


def _best_category(score_details: dict) -> tuple[str | None, int]:
    best_cat, best_score = None, 0
    for cat, detail in (score_details or {}).items():
        if not isinstance(detail, dict):
            continue
        try:
            s = int(detail.get("score", 0) or 0)
        except (TypeError, ValueError):
            s = 0
        if s > best_score:
            best_cat, best_score = cat, s
    return best_cat, best_score


def _resolve_commercial(category: str | None, assignment_rules: dict, configured_categories: dict) -> str | None:
    if not category:
        return None
    rule = (assignment_rules or {}).get(category)
    if isinstance(rule, str):
        return rule.strip() or None
    if isinstance(rule, (list, tuple)):
        return next((str(i).strip() for i in rule if i and str(i).strip()), None)
    if isinstance(rule, dict):
        val = rule.get("commercial") or rule.get("nom")
        if val:
            return str(val).strip() or None
    cat_cfg = (configured_categories or {}).get(category, {})
    if isinstance(cat_cfg, dict):
        fb = cat_cfg.get("commercial")
        if fb:
            return str(fb).strip() or None
    return None


def _resolve_commercial_id(db, company_id: int, category: str | None, assignment_rules: dict, configured_categories: dict) -> int | None:
    if company_id is None:
        raise ValueError("company_id est obligatoire.")
    nom = _resolve_commercial(category, assignment_rules, configured_categories)
    if not nom:
        return None
    commercial = (
        db.query(Commercial)
        .filter(Commercial.company_id == company_id, Commercial.nom == nom, Commercial.actif.is_(True))
        .order_by(Commercial.id)
        .first()
    )
    return commercial.id if commercial is not None else None


def _tender_to_raw(tender: Sotradies) -> SotradiesRaw:
    return SotradiesRaw(
        source=tender.source,
        objet=tender.objet,
        acheteur=tender.acheteur,
        categorie=tender.categorie,
        date_publication=tender.date_publication,
        date_limite=tender.date_limite,
        reference=tender.reference,
        budget_estime=(float(tender.budget_estime) if tender.budget_estime is not None else None),
        lien=tender.lien,
    )


def _alert_scraper_failure(source_name: str) -> None:
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            f"⚠️ Scraper {source_name} : 0 résultat",
            f"<p>Le scraper <b>{html.escape(source_name)}</b> n'a retourné aucun marché.</p>",
        )
    except Exception:
        pass


def _already_enriched(db, tender_id: str) -> bool:
    """Vrai si l'IA a déjà tenté d'enrichir cette offre (succès ou échec)."""
    return (
        db.query(PipelineLog.id)
        .filter(PipelineLog.tender_id == tender_id, PipelineLog.event_type == "AI_ENRICHED")
        .first()
        is not None
    )


def _score_for_all_companies(db, tender: Sotradies, source_name: str, run_id: str) -> dict:
    summary = {"any_retained": False, "scored": 0}
    ai_cache = {}

    normalized = source_name.lower()
    if normalized.startswith("web_"):
        try:
            source_id = int(normalized.replace("web_", ""))
        except ValueError:
            return summary
        source = db.get(ScrapingSource, source_id)
    else:
        source = db.query(ScrapingSource).filter(ScrapingSource.type == "dedie", func.lower(ScrapingSource.nom) == source_name.lower()).one_or_none()

    if source is None:
        return summary

    subscriptions = db.query(CompanySource).filter(CompanySource.source_id == source.id, CompanySource.actif.is_(True)).all()
    if not subscriptions:
        return summary

    raw = _tender_to_raw(tender)

    for sub in subscriptions:
        company_id = sub.company_id
        already = db.query(CompanyTender).filter_by(company_id=company_id, tender_id=tender.id).first()
        if already:
            if already.decision == "retenu":
                summary["any_retained"] = True
            continue

        config = db.query(Configuration).filter(Configuration.company_id == company_id).one_or_none()
        if config is None or not config.categories:
            continue

        categories = config.categories or {}
        exclusions = config.exclusion_keywords or []
        matched_exclusion = first_matching_keyword(tender.objet, exclusions)

        if matched_exclusion:
            score_details = {
                cat: {"score": 0, "mots_cles_matches": [], "methode": "exclusion", "mot_exclusion": matched_exclusion}
                for cat in categories
            }
            score, categorie = 0, None
        else:
            try:
                score_details = score_tender_full(raw, categories, exclusions) or {}
            except Exception as exc:
                score_details = {}
                log_pipeline_event(
                    db, run_id, "COMPANY_SCORING_ERROR",
                    source=tender.source, tender_id=tender.id,
                    message="Erreur de scoring pour ce client",
                    payload={"company_id": company_id, "error": type(exc).__name__},
                )
            categorie, score = _best_category(score_details)

        decision = "retenu" if score >= config.score_decision_threshold else "rejete"
        if decision == "retenu":
            summary["any_retained"] = True
        summary["scored"] += 1

        commercial_id = _resolve_commercial_id(db, company_id, categorie, config.assignment_rules or {}, categories)
        acheteur_connu = "Inconnu"
        try:
            acheteur_connu = match_buyer(tender.acheteur, company_id=company_id) or "Inconnu"
        except Exception:
            pass

        db.add(CompanyTender(
            company_id=company_id, tender_id=tender.id, score=score, categorie=categorie,
            score_details=score_details, decision=decision, statut="nouveau",
            commercial_id=commercial_id, acheteur_connu=acheteur_connu,
        ))

        log_pipeline_event(
            db, run_id, "COMPANY_SCORED", source=tender.source, tender_id=tender.id,
            payload={"company_id": company_id, "score": score, "decision": decision, "categorie": categorie, "commercial_id": commercial_id, "mot_exclusion": matched_exclusion}
        )

    return summary


def _enrich_with_ai(db, record: Sotradies, effective_source: str, tender_id: str, run_id: str) -> dict:
    ai_result = dict(_EMPTY_RESULT_FILTER)
    errors = 0
    try:
        time.sleep(2)
        detail_text = fetch_detail_text(effective_source, record.lien)
        dump_path = dump_tender_to_txt(tender_id, record, detail_text)
        extraction = filter_and_extract(dump_path.read_text(encoding="utf-8"), {})
        if isinstance(extraction, dict) and extraction.get("raison") != "Erreur technique IA (locale)":
            ai_result = {**ai_result, **{k: v for k, v in extraction.items() if v not in (None, "", [])}}
        else:
            errors += 1
    except Exception:
        errors += 1

    for field in (
        "description_detaillee", "budget_detecte", "duree_execution", "montant_cautionnement",
        "type_marche", "procedure_passation", "region_execution", "date_debut_execution",
        "date_ouverture_offres", "lieu_ouverture_offres", "caractere_prix",
    ):
        value = ai_result.get(field)
        if value not in (None, "", []):
            setattr(record, field, value)

    log_pipeline_event(db, run_id, "AI_ENRICHED", source=effective_source, tender_id=tender_id, payload={"errors": errors})
    return {"errors": errors}

def _reset_ai_cache() -> None:
    """Vide le cache IA entre deux runs."""
    try:
        from app.services.scoring_orchestrator import _AI_CALL_CACHE
        _AI_CALL_CACHE.clear()
    except Exception:
        pass


def run_pipeline(
    target_date: date | None = None,
    company_id: int | None = None,
) -> dict:
    """
    Pipeline complet.

    company_id : si fourni, ne scrape que les sources de CE client
                 (utilisé après inscription pour un run immédiat).
    """
    run_id = uuid4().hex
    _reset_ai_cache()
    target_date = target_date or datetime.now().date()
    scrapers = _build_scrapers(company_id=company_id)

    total_nouveaux = 0
    total_doublons = 0
    total_hors_date = 0
    total_sans_date = 0
    total_enrichis = 0
    ai_errors = 0
    executed_sources = 0
    seen_this_run: set[str] = set()

    with session_scope() as db:
        log_pipeline_event(
            db, run_id, "RUN_STARTED",
            message="Démarrage du pipeline",
            payload={
                "target_date": target_date.isoformat(),
                "company_id": company_id,
                "scrapers": [
                    getattr(s, "source_name", s.__class__.__name__)
                    for s in scrapers
                ],
            },
        )

        for scraper in scrapers:
            source_name = getattr(
                scraper, "source_name", scraper.__class__.__name__
            )
            executed_sources += 1

            log_pipeline_event(
                db, run_id, "SCRAPE_STARTED",
                source=source_name, message="Début scraping",
            )

            try:
                all_tenders = fetch_with_cache(scraper)
            except Exception as exc:
                print(f"[pipeline] ❌ Erreur scraper {source_name}: {exc}")
                log_pipeline_event(
                    db, run_id, "SCRAPER_ERROR",
                    source=source_name,
                    payload={"error": type(exc).__name__, "details": str(exc)},
                )
                _alert_scraper_failure(source_name)
                continue

            log_pipeline_event(
                db, run_id, "SCRAPE_FINISHED",
                source=source_name,
                payload={"raw_count": len(all_tenders)},
            )

            if not all_tenders:
                if not source_name.startswith("web_"):
                    _alert_scraper_failure(source_name)
                else:
                    print(f"[pipeline] ℹ️ {source_name} : 0 résultat")
                log_pipeline_event(
                    db, run_id, "SCRAPER_EMPTY",
                    source=source_name, message="0 marché retourné",
                )
                continue

            # ── Filtrage : offres du jour OU encore ouvertes ──
            tenders, sans_date = filter_today_only(all_tenders, target_date)
            hors_date = len(all_tenders) - len(tenders) - sans_date
            total_hors_date += hors_date
            total_sans_date += sans_date

            log_pipeline_event(
                db, run_id, "FILTER_DATE_SUMMARY",
                source=source_name,
                payload={
                    "target_date": target_date.isoformat(),
                    "raw_count": len(all_tenders),
                    "kept_count": len(tenders),
                    "hors_date": hors_date,
                    "sans_date": sans_date,
                },
            )
            print(
                f"[pipeline] {source_name} : "
                f"{len(tenders)} marché(s) gardé(s) sur {len(all_tenders)}"
            )

            # ── Traitement de chaque marché ──
            for tender in tenders:
                effective_source = tender.source or source_name
                tender_id = compute_hash(tender, fallback_source=source_name)

                # Déduplication intra-run
                if tender_id in seen_this_run:
                    total_doublons += 1
                    continue
                seen_this_run.add(tender_id)

                # Savepoint : une erreur sur une offre n'annule pas le run
                tmp_nouveaux = tmp_doublons = tmp_enrichis = tmp_ai_errors = 0

                try:
                    with db.begin_nested():
                        existing = (
                            db.query(Sotradies).filter_by(id=tender_id).first()
                        )

                        if existing:
                            tmp_doublons = 1

                            # Mise à jour uniquement si les nouvelles valeurs existent
                            changed = False
                            if (
                                tender.date_limite is not None
                                and existing.date_limite != tender.date_limite
                            ):
                                existing.date_limite = tender.date_limite
                                changed = True

                            if tender.budget_estime is not None:
                                new_budget = Decimal(
                                    str(tender.budget_estime)
                                ).quantize(Decimal("0.01"))
                                if existing.budget_estime != new_budget:
                                    existing.budget_estime = new_budget
                                    changed = True

                            if changed:
                                existing.date_derniere_action = (
                                    datetime.now(UTC).replace(tzinfo=None)
                                )
                                log_pipeline_event(
                                    db, run_id, "UPDATED_EXISTING",
                                    source=effective_source,
                                    tender_id=tender_id,
                                    payload={"objet": existing.objet},
                                )
                            else:
                                log_pipeline_event(
                                    db, run_id, "DUPLICATE_DB",
                                    source=effective_source,
                                    tender_id=tender_id,
                                )

                            # Rescorer pour les nouveaux abonnés
                            existing_summary = _score_for_all_companies(
                                db, existing, effective_source, run_id
                            )

                            # Enrichissement IA si jamais fait et un client retient
                            if (
                                existing_summary["any_retained"]
                                and not _already_enriched(db, existing.id)
                            ):
                                enrich_result = _enrich_with_ai(
                                    db, existing, effective_source,
                                    existing.id, run_id,
                                )
                                tmp_ai_errors = enrich_result["errors"]
                                tmp_enrichis = 1

                        else:
                            # ── Nouvelle offre ──
                            tmp_nouveaux = 1

                            record = Sotradies(
                                id=tender_id,
                                reference=tender.reference,
                                objet=tender.objet,
                                acheteur=tender.acheteur or "Non précisé",
                                categorie=tender.categorie,
                                date_publication=tender.date_publication,
                                date_limite=tender.date_limite,
                                budget_estime=tender.budget_estime,
                                source=effective_source,
                                lien=tender.lien,
                                statut="nouveau",
                                commercial_assigne=None,
                                score_details=None,
                                acheteur_connu=None,
                                # Champs enrichis par le scraper universel
                                description_detaillee=getattr(
                                    tender, "description_detaillee", None
                                ),
                                type_marche=getattr(
                                    tender, "type_marche", None
                                ),
                                procedure_passation=getattr(
                                    tender, "procedure_passation", None
                                ),
                                region_execution=getattr(
                                    tender, "region_execution", None
                                ),
                                lieu_ouverture_offres=getattr(
                                    tender, "lieu_ouverture_offres", None
                                ),
                                caractere_prix=getattr(
                                    tender, "caractere_prix", None
                                ),
                            )
                            db.add(record)
                            db.flush()

                            log_pipeline_event(
                                db, run_id, "INSERTED",
                                source=effective_source,
                                tender_id=tender_id,
                                payload={"objet": tender.objet},
                            )

                            # Phase 2 : scoring par client
                            company_summary = _score_for_all_companies(
                                db, record, effective_source, run_id
                            )

                            log_pipeline_event(
                                db, run_id,
                                "RETAINED_BY_SOME_CLIENT"
                                if company_summary["any_retained"]
                                else "REJECTED_BY_ALL_CLIENTS",
                                source=effective_source,
                                tender_id=tender_id,
                                payload=company_summary,
                            )

                            # Phase 3 : enrichissement IA (une seule fois,
                            # seulement si un client a retenu l'offre,
                            # et seulement si le scraper universel n'a
                            # pas déjà enrichi depuis la page de détail)
                            already_enriched_by_scraper = bool(
                                getattr(tender, "description_detaillee", None)
                            )

                            if (
                                company_summary["any_retained"]
                                and not already_enriched_by_scraper
                            ):
                                enrich_result = _enrich_with_ai(
                                    db, record, effective_source,
                                    tender_id, run_id,
                                )
                                tmp_ai_errors = enrich_result["errors"]
                                tmp_enrichis = 1

                    # Compteurs mis à jour seulement si le savepoint a validé
                    total_nouveaux += tmp_nouveaux
                    total_doublons += tmp_doublons
                    total_enrichis += tmp_enrichis
                    ai_errors += tmp_ai_errors

                except Exception as exc:
                    print(
                        f"[pipeline] ❌ Erreur isolée sur {tender_id}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    log_pipeline_event(
                        db, run_id, "TENDER_PROCESSING_ERROR",
                        source=effective_source,
                        tender_id=tender_id,
                        payload={
                            "error": type(exc).__name__,
                            "details": str(exc)[:500],
                        },
                    )

        # ── Mise à jour last_scraped des sources universelles ──
        universal_ids = [
            int(s.source_name.replace("web_", ""))
            for s in scrapers
            if hasattr(s, "source_name")
            and s.source_name.startswith("web_")
        ]
        if universal_ids:
            db.query(ScrapingSource).filter(
                ScrapingSource.id.in_(universal_ids)
            ).update(
                {"last_scraped": datetime.now(UTC).replace(tzinfo=None)},
                synchronize_session=False,
            )

        if ai_errors:
            print(f"[pipeline] ⚠️ {ai_errors} échec(s) IA.")
            try:
                send_email(
                    settings.ADMIN_ALERT_EMAIL,
                    f"⚠️ Pipeline : {ai_errors} échec(s) IA",
                    f"<p>{html.escape(str(ai_errors))} échec(s) IA.</p>",
                )
            except Exception:
                pass

        log_pipeline_event(
            db, run_id, "RUN_FINISHED",
            message="Fin du pipeline",
            payload={
                "target_date": target_date.isoformat(),
                "company_id": company_id,
                "nouveaux": total_nouveaux,
                "doublons": total_doublons,
                "hors_date": total_hors_date,
                "sans_date": total_sans_date,
                "enrichis_ia": total_enrichis,
                "ai_errors": ai_errors,
                "sources_executees": executed_sources,
                "sources_chargees": len(scrapers),
            },
        )

    cache_delete_pattern("tenders:list:*")

    summary = {
        "run_id": run_id,
        "date_ciblee": target_date.isoformat(),
        "nouveaux": total_nouveaux,
        "doublons": total_doublons,
        "hors_date": total_hors_date,
        "sans_date": total_sans_date,
        "enrichis_ia": total_enrichis,
        "ai_errors": ai_errors,
        "sources_chargees": len(scrapers),
        "sources_executees": executed_sources,
    }
    print(f"\n[pipeline] Résumé : {summary}")
    return summary