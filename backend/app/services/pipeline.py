"""
Pipeline complet :

Phase 1 — Collecte globale :
scraping → filtre date → déduplication → scoring global → insertion sotradies

Phase 2 — Scoring par client :
pour chaque offre insérée, score avec la config de chaque client abonné
→ insertion company_tenders

Réutilisable en CLI et comme tâche Celery.
"""

import hashlib
import time
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import func
from unidecode import unidecode

from app.core.cache import cache_delete_pattern, cache_get, cache_set
from app.core.config import settings
from app.core.database import session_scope

from app.models.company_source import CompanySource
from app.models.company_tender import CompanyTender
from app.models.commercial import Commercial
from app.models.scraping_source import ScrapingSource
from app.models.sotradies import Sotradies

from app.schemas.sotradies import SotradiesRaw

from app.services.ai_filter_and_extract import (
    _EMPTY_RESULT as _EMPTY_RESULT_FILTER,
    filter_and_extract,
)
from app.services.buyer_matcher import match_buyer
from app.services.config_service import get_or_create_config
from app.services.detail_fetcher import fetch_detail_text
from app.services.mailer import send_email
from app.services.pipeline_logger import log_pipeline_event
from app.services.raw_dump import dump_tender_to_txt
from app.services.scoring_orchestrator import score_tender_full

from app.services.scrapers.onmp_scraper import OnmpScraper
from app.services.scrapers.tuneps_scraper import TunepsScraper
from app.services.scrapers.universal_scraper import UniversalScraper


SCRAPE_CACHE_TTL = 25 * 60


# ───────────────────────────────────────────────────────────
# Chargement des scrapers
# ───────────────────────────────────────────────────────────

def _load_universal_scrapers() -> list[UniversalScraper]:
    """Charge les sources universelles actives. Session fermée avant le scraping."""
    with session_scope() as db:
        rows = (
            db.query(
                ScrapingSource.id,
                ScrapingSource.url,
                ScrapingSource.use_browser,
                ScrapingSource.max_pages,
                ScrapingSource.nom,
            )
            .filter(
                ScrapingSource.actif.is_(True),
                ScrapingSource.url.isnot(None),
                ScrapingSource.type == "universel",   # ← AJOUT INDISPENSABLE
            )
            .order_by(ScrapingSource.id.asc())
            .all()
        )

        source_specs = [
            {
                "id": row.id,
                "url": str(row.url).strip(),
                "use_browser": bool(row.use_browser),
                "max_pages": int(row.max_pages or 3),
                "nom": row.nom,
            }
            for row in rows
            if row.url and str(row.url).strip()
        ]

    return [
        UniversalScraper(
            source_name=f"web_{spec['id']}",
            url=spec["url"],
            use_browser=spec["use_browser"],
            max_pages=spec["max_pages"],
        )
        for spec in source_specs
    ]


def _build_scrapers() -> list:
    dedicated = [OnmpScraper(), TunepsScraper()]
    universal = _load_universal_scrapers()

    if universal:
        print(f"[pipeline] {len(universal)} source(s) universelle(s) ajoutée(s)")
    else:
        print("[pipeline] Aucune source universelle active.")

    return [*dedicated, *universal]


# ───────────────────────────────────────────────────────────
# Cache du scraping
# ───────────────────────────────────────────────────────────

def fetch_with_cache(scraper) -> list[SotradiesRaw]:
    source_name = getattr(
        scraper, "source_name", scraper.__class__.__name__
    )
    cache_key = f"scrape:{source_name}"
    cached = cache_get(cache_key)

    if cached is not None:
        print(f"[cache] {source_name} : servi depuis le cache")
        return [
            item if isinstance(item, SotradiesRaw)
            else SotradiesRaw(**item)
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
        else:
            raise TypeError(
                f"Type invalide retourné par {source_name}: "
                f"{type(item).__name__}"
            )

    cache_set(
        cache_key,
        [t.model_dump(mode="json") for t in tenders],
        SCRAPE_CACHE_TTL,
    )
    return tenders


# ───────────────────────────────────────────────────────────
# Utilitaires
# ───────────────────────────────────────────────────────────

def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(unidecode(str(value)).lower().strip().split())


def _iso_or_none(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def compute_hash(
    tender: SotradiesRaw,
    fallback_source: str | None = None,
) -> str:
    parts = [
        _normalize(tender.source or fallback_source),
        _normalize(tender.reference),
        _normalize(tender.objet),
        _normalize(tender.acheteur),
        _normalize(tender.categorie),
        str(tender.date_publication or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def filter_today_only(
    tenders: list[SotradiesRaw],
    target_date: date,
) -> tuple[list[SotradiesRaw], int]:
    kept, sans_date = [], 0
    for t in tenders:
        if t.date_publication is None:
            sans_date += 1
            continue
        pub = (
            t.date_publication.date()
            if isinstance(t.date_publication, datetime)
            else t.date_publication
        )
        if pub == target_date:
            kept.append(t)
    return kept, sans_date


def _source_is_active(active_sources: dict, source_name: str) -> bool:
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
    norm_cfg = {str(k).strip().lower(): v for k, v in active_sources.items()}

    configured = next(
        (norm_cfg[k] for k in keys if k in norm_cfg),
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


def _resolve_commercial(
    category: str | None,
    assignment_rules: dict,
    configured_categories: dict,
) -> str | None:
    """Retourne le nom du commercial pour une catégorie (V1 — par nom)."""
    if not category:
        return None

    rule = (assignment_rules or {}).get(category)

    if isinstance(rule, str):
        return rule.strip() or None
    if isinstance(rule, (list, tuple)):
        return next(
            (str(i).strip() for i in rule if i and str(i).strip()),
            None,
        )
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


def _resolve_commercial_id(
    db,
    company_id: int,
    category: str | None,
    assignment_rules: dict,
    configured_categories: dict,
) -> int | None:
    """
    Retourne l'ID du commercial SQLAlchemy pour un client donné.

    Cherche d'abord dans les assignment_rules, puis dans la catégorie.
    Le commercial doit appartenir au même client.
    """
    nom = _resolve_commercial(category, assignment_rules, configured_categories)

    if not nom:
        return None

    commercial = (
        db.query(Commercial)
        .filter(
            Commercial.nom == nom,
            Commercial.company_id == company_id,
            Commercial.actif.is_(True),
        )
        .first()
    )

    if commercial is None:
        # Tentative sans company_id (données historiques non encore rattachées)
        commercial = (
            db.query(Commercial)
            .filter(
                Commercial.nom == nom,
                Commercial.actif.is_(True),
            )
            .first()
        )

    return commercial.id if commercial else None


def _tender_to_raw(tender: Sotradies) -> SotradiesRaw:
    """Convertit un enregistrement Sotradies en SotradiesRaw pour le scoring."""
    return SotradiesRaw(
        source=tender.source,
        objet=tender.objet,
        acheteur=tender.acheteur,
        categorie=tender.categorie,
        date_publication=tender.date_publication,
        date_limite=tender.date_limite,
        reference=tender.reference,
        budget_estime=(
            float(tender.budget_estime)
            if tender.budget_estime is not None
            else None
        ),
        lien=tender.lien,
    )


# ───────────────────────────────────────────────────────────
# Alertes techniques
# ───────────────────────────────────────────────────────────

def _alert_scraper_failure(source_name: str) -> None:
    print(f"[pipeline] ⚠️ {source_name} : 0 marché — site possiblement cassé.")
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            f"⚠️ Scraper {source_name} : 0 résultat",
            f"""<p>Le scraper <b>{source_name}</b> n'a retourné aucun marché.</p>
                <p>Causes possibles : structure modifiée, inaccessible,
                blocage IP, identifiants expirés.</p>""",
        )
    except Exception as exc:
        print(f"[pipeline] Échec alerte technique : {exc}")


def _alert_empty_configuration() -> None:
    print("[pipeline] ⚠️ Aucune catégorie configurée en base.")
    try:
        send_email(
            settings.ADMIN_ALERT_EMAIL,
            "⚠️ Configuration vide",
            "<p>Aucune catégorie configurée. Action requise.</p>",
        )
    except Exception as exc:
        print(f"[pipeline] Échec alerte configuration : {exc}")


# ───────────────────────────────────────────────────────────
# Phase 2 — Scoring par client
# ───────────────────────────────────────────────────────────

def _score_for_all_companies(
    db,
    tender: Sotradies,
    source_name: str,
    run_id: str,
    seuil_global: int,
) -> None:
    """
    Score un marché inséré pour chaque client abonné à sa source.

    La source est identifiée par son nom canonique (onmp, tuneps, web_X).
    Les résultats sont insérés dans company_tenders.
    """
    # Trouver la ligne scraping_sources correspondante
    normalized = source_name.lower()

    if normalized.startswith("web_"):
        try:
            source_id = int(normalized.replace("web_", ""))
        except ValueError:
            return

        source = db.query(ScrapingSource).get(source_id)
    else:
        source = (
            db.query(ScrapingSource)
            .filter(
                func.lower(ScrapingSource.nom) == func.lower(source_name)
            )
            .first()
        )

    if source is None:
        return

    # Clients abonnés à cette source
    subscriptions = (
        db.query(CompanySource)
        .filter(
            CompanySource.source_id == source.id,
            CompanySource.actif.is_(True),
        )
        .all()
    )

    if not subscriptions:
        return

    raw = _tender_to_raw(tender)

    for sub in subscriptions:
        company_id = sub.company_id

        # Ne pas recalculer si déjà présent
        already = (
            db.query(CompanyTender)
            .filter_by(
                company_id=company_id,
                tender_id=tender.id,
            )
            .first()
        )

        if already:
            continue

        config = get_or_create_config(db, company_id=company_id)
        categories = config.categories or {}
        exclusions = config.exclusion_keywords or []

        # Vérifier l'exclusion
        text_check = _normalize(tender.objet)
        matched_exclusion = next(
            (kw for kw in exclusions if _normalize(kw) in text_check),
            None,
        )

        if matched_exclusion:
            score_details = {
                cat: {
                    "score": 0,
                    "mots_cles_matches": [],
                    "methode": "exclusion",
                }
                for cat in categories
            }
            score, categorie = 0, None
        else:
            try:
                score_details = score_tender_full(raw, categories, exclusions) or {}
            except Exception:
                score_details = {}

            categorie, score = _best_category(score_details)

        decision = (
            "retenu"
            if score >= config.score_decision_threshold
            else "rejete"
        )

        commercial_id = _resolve_commercial_id(
            db,
            company_id,
            categorie,
            config.assignment_rules or {},
            categories,
        )

        try:
            acheteur_connu = match_buyer(
                tender.acheteur,
                company_id=company_id,
            ) or "Inconnu"
        except Exception:
            acheteur_connu = "Inconnu"

        db.add(CompanyTender(
            company_id=company_id,
            tender_id=tender.id,
            score=score,
            categorie=categorie,
            score_details=score_details,
            decision=decision,
            statut="nouveau",
            commercial_id=commercial_id,
            acheteur_connu=acheteur_connu,
        ))

        log_pipeline_event(
            db,
            run_id,
            "COMPANY_SCORED",
            source=tender.source,
            tender_id=tender.id,
            payload={
                "company_id": company_id,
                "score": score,
                "decision": decision,
                "categorie": categorie,
                "commercial_id": commercial_id,
            },
        )


# ───────────────────────────────────────────────────────────
# Pipeline principal
# ───────────────────────────────────────────────────────────

def run_pipeline(target_date: date | None = None) -> dict:
    run_id = uuid4().hex
    target_date = target_date or datetime.now().date()

    print(f"[pipeline] Run ID : {run_id}")
    print(f"[pipeline] Date ciblée : {target_date.isoformat()}")

    # Construction des scrapers AVANT la session principale
    scrapers = _build_scrapers()

    total_nouveaux = 0
    total_doublons = 0
    total_hors_date = 0
    total_sans_date = 0
    ai_errors = 0
    executed_sources = 0
    retenus, non_retenus = [], []
    seen_this_run: set[str] = set()

    # Valeur par défaut avant lecture de la config
    seuil_alerte = settings.RELEVANCE_INSTANT_ALERT_THRESHOLD

    with session_scope() as db:

        # ── Configuration globale (mono-client ou premier client) ──
        config = get_or_create_config(db)
        seuil_retention = config.score_decision_threshold
        seuil_alerte = config.score_instant_alert_threshold
        configured_categories = config.categories or {}
        configured_exclusions = [
            str(kw).strip()
            for kw in (config.exclusion_keywords or [])
            if str(kw).strip()
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
                "scrapers": [
                    getattr(s, "source_name", s.__class__.__name__)
                    for s in scrapers
                ],
            },
        )

        if not configured_categories:
            _alert_empty_configuration()
            log_pipeline_event(db, run_id, "CONFIG_EMPTY",
                               message="Aucune catégorie configurée")

        # ═══════════════════════════════════════════════════════
        # BOUCLE SUR LES SCRAPERS
        # ═══════════════════════════════════════════════════════

        for scraper in scrapers:
            source_name = getattr(
                scraper, "source_name", scraper.__class__.__name__
            )

            if not _source_is_active(active_sources, source_name):
                print(f"[pipeline] Source désactivée : {source_name}")
                log_pipeline_event(
                    db, run_id, "SOURCE_DISABLED",
                    source=source_name,
                    message="Désactivée par configuration",
                )
                continue

            executed_sources += 1
            print(f"[pipeline] Source : {source_name}")

            log_pipeline_event(db, run_id, "SCRAPE_STARTED",
                               source=source_name, message="Début scraping")

            try:
                all_tenders = fetch_with_cache(scraper)
            except Exception as exc:
                print(f"[pipeline] ❌ Erreur scraper {source_name}: {exc}")
                log_pipeline_event(
                    db, run_id, "SCRAPER_ERROR",
                    source=source_name,
                    message=f"Erreur scraper",
                    payload={"error": str(exc)},
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
                    print(
                        f"[pipeline] ℹ️ {source_name} : "
                        "0 résultat (source universelle)"
                    )
                log_pipeline_event(
                    db, run_id, "SCRAPER_EMPTY",
                    source=source_name, message="0 marché retourné",
                )
                continue

            # ── Filtrage par date ──
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
                f"{len(tenders)} marché(s) du {target_date.isoformat()}"
            )

            # ═══════════════════════════════════════════════════════
            # TRAITEMENT DE CHAQUE MARCHÉ
            # ═══════════════════════════════════════════════════════

            for tender in tenders:
                effective_source = tender.source or source_name
                tender_id = compute_hash(tender, fallback_source=source_name)

                # ── Déduplication intra-run ──
                if tender_id in seen_this_run:
                    total_doublons += 1
                    log_pipeline_event(
                        db, run_id, "DUPLICATE_RUN",
                        source=effective_source, tender_id=tender_id,
                        payload={"objet": tender.objet},
                    )
                    continue

                seen_this_run.add(tender_id)

                # ── Déduplication base de données ──
                existing = (
                    db.query(Sotradies).filter_by(id=tender_id).first()
                )

                if existing:
                    total_doublons += 1
                    changed = False

                    if existing.date_limite != tender.date_limite:
                        existing.date_limite = tender.date_limite
                        changed = True
                    if existing.budget_estime != tender.budget_estime:
                        existing.budget_estime = tender.budget_estime
                        changed = True

                    if changed:
                        existing.date_derniere_action = (
                            datetime.now(UTC).replace(tzinfo=None)
                        )
                        log_pipeline_event(
                            db, run_id, "UPDATED_EXISTING",
                            source=effective_source, tender_id=tender_id,
                            message="Marché existant mis à jour",
                            payload={"objet": tender.objet},
                        )
                    else:
                        log_pipeline_event(
                            db, run_id, "DUPLICATE_DB",
                            source=effective_source, tender_id=tender_id,
                        )

                    # Phase 2 : scorer pour les clients même si doublon global
                    _score_for_all_companies(
                        db, existing, effective_source, run_id, seuil_retention
                    )
                    continue

                total_nouveaux += 1

                # Valeurs par défaut
                categorie, score, score_details = None, 0, {}
                ai_result = dict(_EMPTY_RESULT_FILTER)

                # ── Exclusion par mots-clés négatifs ──
                text_check = _normalize(tender.objet)
                matched_exclusion = next(
                    (kw for kw in configured_exclusions
                     if _normalize(kw) in text_check),
                    None,
                )

                if matched_exclusion:
                    score_details = {
                        cat: {
                            "score": 0,
                            "mots_cles_matches": [],
                            "methode": "exclusion",
                        }
                        for cat in configured_categories
                    }
                    log_pipeline_event(
                        db, run_id, "EXCLUDED_KEYWORD",
                        source=effective_source, tender_id=tender_id,
                        payload={
                            "objet": tender.objet,
                            "keyword": matched_exclusion,
                        },
                    )

                else:
                    # ── Scoring ──
                    try:
                        score_details = score_tender_full(
                            tender,
                            configured_categories,
                            configured_exclusions,
                        ) or {}
                    except Exception as exc:
                        score_details = {}
                        ai_errors += 1
                        print(
                            f"[pipeline] ❌ Erreur scoring "
                            f"{tender_id}: {exc}"
                        )
                        log_pipeline_event(
                            db, run_id, "SCORING_ERROR",
                            source=effective_source, tender_id=tender_id,
                            payload={"objet": tender.objet, "error": str(exc)},
                        )

                    categorie, score = _best_category(score_details)

                    if any(
                        isinstance(d, dict)
                        and d.get("raison_ia") == "Erreur technique IA (locale)"
                        for d in score_details.values()
                    ):
                        ai_errors += 1

                    log_pipeline_event(
                        db, run_id, "SCORED",
                        source=effective_source, tender_id=tender_id,
                        payload={
                            "categorie": categorie,
                            "score": score,
                        },
                    )

                    # ── Extraction IA (marchés retenus uniquement) ──
                    if score >= seuil_retention:
                        try:
                            time.sleep(2)
                            detail_text = fetch_detail_text(
                                effective_source, tender.lien
                            )
                            dump_path = dump_tender_to_txt(
                                tender_id, tender, detail_text
                            )

                            extraction = filter_and_extract(
                                dump_path.read_text(encoding="utf-8"),
                                configured_categories,
                            )

                            if (
                                isinstance(extraction, dict)
                                and extraction.get("raison")
                                != "Erreur technique IA (locale)"
                            ):
                                ai_result = {
                                    **ai_result,
                                    **{
                                        k: v
                                        for k, v in extraction.items()
                                        if v not in (None, "", [])
                                    },
                                }
                            else:
                                ai_errors += 1

                        except Exception as exc:
                            ai_errors += 1
                            print(
                                f"[pipeline] ⚠️ Extraction impossible "
                                f"{tender_id}: {exc}"
                            )

                # ── Assignation commerciale (V1 — par nom) ──
                commercial = _resolve_commercial(
                    categorie, assignment_rules, configured_categories
                )

                try:
                    acheteur_connu = match_buyer(tender.acheteur) or "Inconnu"
                except Exception:
                    acheteur_connu = "Inconnu"

                final_status = (
                    "retenu" if score >= seuil_retention else "nouveau"
                )

                # ── Insertion globale dans sotradies ──
                record = Sotradies(
                    id=tender_id,
                    reference=tender.reference,
                    objet=tender.objet,
                    acheteur=tender.acheteur,
                    categorie=categorie or tender.categorie,
                    date_publication=tender.date_publication,
                    date_limite=tender.date_limite,
                    budget_estime=tender.budget_estime,
                    source=effective_source,
                    lien=tender.lien,
                    statut=final_status,
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
                db.flush()  # obtenir l'id avant Phase 2

                log_pipeline_event(
                    db, run_id, "INSERTED",
                    source=effective_source, tender_id=tender_id,
                    payload={
                        "objet": tender.objet,
                        "score": score,
                        "categorie": categorie,
                        "statut": final_status,
                    },
                )

                # ── Phase 2 : Scoring par client ──
                _score_for_all_companies(
                    db, record, effective_source, run_id, seuil_retention
                )

                retained = score >= seuil_retention

                log_pipeline_event(
                    db, run_id,
                    "RETAINED" if retained else "REJECTED",
                    source=effective_source, tender_id=tender_id,
                    payload={
                        "score": score,
                        "seuil": seuil_retention,
                    },
                )

                entry = (
                    score, categorie, commercial,
                    effective_source, tender.objet, acheteur_connu,
                )
                (retenus if retained else non_retenus).append(entry)

        # ── Mise à jour last_scraped ──
        universal_ids = [
            int(s.source_name.replace("web_", ""))
            for s in scrapers
            if hasattr(s, "source_name") and s.source_name.startswith("web_")
        ]
        if universal_ids:
            db.query(ScrapingSource).filter(
                ScrapingSource.id.in_(universal_ids)
            ).update(
                {"last_scraped": datetime.now(UTC).replace(tzinfo=None)},
                synchronize_session=False,
            )

        # ── Alerte erreurs IA ──
        if ai_errors:
            print(f"[pipeline] ⚠️ {ai_errors} échec(s) IA pendant ce run.")
            try:
                send_email(
                    settings.ADMIN_ALERT_EMAIL,
                    f"⚠️ Pipeline : {ai_errors} échec(s) IA",
                    f"""<p>{ai_errors} échec(s) IA.
                    Modèle : <code>{settings.OLLAMA_MODEL}</code>.</p>""",
                )
            except Exception:
                pass

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
                "sources_executees": executed_sources,
                "sources_chargees": len(scrapers),
            },
        )

    # ── Hors session ──
    cache_delete_pattern("tenders:list:*")
    retenus.sort(key=lambda e: e[0], reverse=True)

    print(f"\n{'=' * 90}")
    print(f"RETENUS ({len(retenus)}) — triés par score décroissant")
    print(f"{'=' * 90}")
    for score, cat, com, src, objet, ac in retenus:
        alerte = " 🔴" if score > seuil_alerte else ""
        connu = " ⭐ CONNU" if ac == "Oui" else ""
        print(
            f"[{score}% | {cat or 'N/A'} | {com or 'NON ASSIGNÉ'} | "
            f"{src}]{alerte}{connu} {(objet or '')[:60]}"
        )

    summary = {
        "run_id": run_id,
        "date_ciblee": target_date.isoformat(),
        "nouveaux": total_nouveaux,
        "doublons": total_doublons,
        "hors_date": total_hors_date,
        "sans_date": total_sans_date,
        "retenus": len(retenus),
        "alertes_instantanees": sum(1 for s, *_ in retenus if s > seuil_alerte),
        "acheteurs_connus": sum(1 for *_, ac in retenus if ac == "Oui"),
        "non_retenus": len(non_retenus),
        "ai_errors": ai_errors,
        "sources_chargees": len(scrapers),
        "sources_executees": executed_sources,
    }

    print(f"\n[pipeline] Résumé : {summary}")
    return summary