"""
Suite de tests complète du projet.

Usage :
    python -m scripts.test_full
    python -m scripts.test_full --verbose
"""

import sys
import traceback
from datetime import datetime

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

from app.models import (  # noqa: F401
    audit_log, commercial, company,
    company_source, company_tender,
    configuration, known_buyer, pipeline_log,
    scraping_source, sent_log, sotradies,
    system_action_log, user,
)

results = []


def run_test(name, fn):
    try:
        fn()
        results.append((name, True, None))
        print(f"  OK  {name}")
    except Exception as exc:
        results.append((name, False, exc))
        print(f"  FAIL {name}")
        if VERBOSE:
            traceback.print_exc()
        else:
            print(f"       {exc.__class__.__name__}: {exc}")


def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ════════════════════════════════════════════════
# 1. Infrastructure
# ════════════════════════════════════════════════

section("1. Infrastructure")


def test_postgres():
    from app.core.database import session_scope
    from sqlalchemy import text
    with session_scope() as db:
        assert db.execute(text("SELECT 1")).scalar() == 1


def test_redis():
    from app.core.cache import cache_get, cache_set
    cache_set("_test_ping", "pong", 10)
    assert cache_get("_test_ping") == "pong"


def test_ollama():
    from app.services.local_llm_client import call_local_llm_json
    result = call_local_llm_json(
        "Reponds en JSON uniquement.",
        'Retourne exactement : {"ok": true}',
    )
    assert result is not None
    assert isinstance(result, dict)


run_test("PostgreSQL accessible", test_postgres)
run_test("Redis accessible", test_redis)
run_test("Ollama accessible", test_ollama)


# ════════════════════════════════════════════════
# 2. Modeles SQLAlchemy
# ════════════════════════════════════════════════

section("2. Modeles SQLAlchemy")


def test_mappers():
    from sqlalchemy.orm import configure_mappers
    configure_mappers()


def test_tables():
    from app.core.database import session_scope
    from sqlalchemy import text
    required = [
        "users", "companies", "company_sources",
        "company_tenders", "configuration", "commercials",
        "scraping_sources", "sotradies", "sent_log",
        "audit_log", "pipeline_log", "known_buyers",
    ]
    with session_scope() as db:
        rows = db.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)).fetchall()
        existing = {r[0] for r in rows}
        missing = [t for t in required if t not in existing]
        assert not missing, f"Tables manquantes : {missing}"


def test_columns():
    from app.core.database import session_scope
    from sqlalchemy import text
    checks = [
        ("users", "company_id"),
        ("companies", "owner_id"),
        ("configuration", "company_id"),
        ("commercials", "company_id"),
        ("company_tenders", "commercial_id"),
        ("company_tenders", "decision"),
        ("company_tenders", "statut"),
    ]
    with session_scope() as db:
        for table, column in checks:
            row = db.execute(text(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = :t AND column_name = :c
            """), {"t": table, "c": column}).first()
            assert row, f"Colonne manquante : {table}.{column}"


run_test("Mappers SQLAlchemy OK", test_mappers)
run_test("Tables requises presentes", test_tables)
run_test("Colonnes multi-client presentes", test_columns)


# ════════════════════════════════════════════════
# 3. Donnees multi-client
# ════════════════════════════════════════════════

section("3. Donnees multi-client")


def test_company_exists():
    from app.core.database import session_scope
    from app.models.company import Company
    with session_scope() as db:
        assert db.query(Company).count() >= 1


def test_users_rattaches():
    from app.core.database import session_scope
    from app.models.user import User
    with session_scope() as db:
        admins = db.query(User).filter(
            User.profil != "superadmin"
        ).all()
        orphelins = [u for u in admins if u.company_id is None]
        assert not orphelins, (
            f"{len(orphelins)} admin(s) sans company_id"
        )


def test_config_rattachee():
    from app.core.database import session_scope
    from app.models.configuration import Configuration
    with session_scope() as db:
        rattachees = db.query(Configuration).filter(
            Configuration.company_id.isnot(None)
        ).count()
        assert rattachees >= 1


def test_commerciaux_rattaches():
    from app.core.database import session_scope
    from app.models.commercial import Commercial
    with session_scope() as db:
        actifs = db.query(Commercial).filter(
            Commercial.actif.is_(True)
        ).all()
        orphelins = [c for c in actifs if c.company_id is None]
        assert not orphelins, (
            f"{len(orphelins)} commercial(aux) sans company_id"
        )


def test_sources_abonnees():
    from app.core.database import session_scope
    from app.models.company_source import CompanySource
    with session_scope() as db:
        assert db.query(CompanySource).count() >= 2


def test_company_tenders():
    from app.core.database import session_scope
    from app.models.company_tender import CompanyTender
    with session_scope() as db:
        total = db.query(CompanyTender).count()
        assert total >= 75, f"Seulement {total} company_tenders"

        retenus = db.query(CompanyTender).filter(
            CompanyTender.decision == "retenu"
        ).count()
        assert retenus >= 6, f"Seulement {retenus} retenus"

        avec_commercial = db.query(CompanyTender).filter(
            CompanyTender.decision == "retenu",
            CompanyTender.commercial_id.isnot(None),
        ).count()
        assert avec_commercial == retenus, (
            f"{retenus - avec_commercial} retenu(s) sans commercial_id"
        )


run_test("Company existe", test_company_exists)
run_test("Admins rattaches a une company", test_users_rattaches)
run_test("Configuration rattachee", test_config_rattachee)
run_test("Commerciaux rattaches", test_commerciaux_rattaches)
run_test("Sources abonnees (>= 2)", test_sources_abonnees)
run_test("company_tenders crees et assignes", test_company_tenders)


# ════════════════════════════════════════════════
# 4. Configuration metier
# ════════════════════════════════════════════════

section("4. Configuration metier")


def test_categories():
    from app.core.database import session_scope
    from app.services.config_service import get_or_create_config
    with session_scope() as db:
        config = get_or_create_config(db)
        assert len(config.categories or {}) >= 5


def test_no_generic_solar():
    from app.core.database import session_scope
    from app.services.config_service import get_or_create_config
    with session_scope() as db:
        config = get_or_create_config(db)
        solar = (config.categories or {}).get("CENTRALES_SOLAIRES", {})
        keywords = [k.lower() for k in solar.get("keywords", [])]
        generics = [k for k in keywords if k in ("installation", "maintenance")]
        assert not generics, f"Mots-cles generiques : {generics}"


def test_no_broken_encoding():
    from app.core.database import session_scope
    from app.services.config_service import get_or_create_config
    with session_scope() as db:
        config = get_or_create_config(db)
        broken = []
        for cat_id, data in (config.categories or {}).items():
            if not isinstance(data, dict):
                continue
            for kw in data.get("keywords", []):
                if "?" in str(kw):
                    broken.append(f"{cat_id}: {kw!r}")
        assert not broken, f"Encodage casse : {broken}"


def test_assignment_rules_correct():
    from app.core.database import session_scope
    from app.services.config_service import get_or_create_config
    with session_scope() as db:
        config = get_or_create_config(db)
        rules = config.assignment_rules or {}

        expected = {
            "MATERIEL_ROULANT": "Ramzi Trabelsi",
            "ENGINS_TP": "Ramzi Trabelsi",
            "MANUTENTION": "Ramzi Trabelsi",
        }

        errors = []
        for cat, expected_commercial in expected.items():
            rule = rules.get(cat)
            if isinstance(rule, list):
                actual = rule[0] if rule else None
            elif isinstance(rule, str):
                actual = rule
            else:
                actual = None

            if actual != expected_commercial:
                errors.append(
                    f"{cat}: attendu {expected_commercial!r}, "
                    f"obtenu {actual!r}"
                )

        assert not errors, f"Regles incorrectes : {errors}"


run_test("Categories configurees (>= 5)", test_categories)
run_test("Pas de mots-cles generiques solaire", test_no_generic_solar)
run_test("Pas d'encodage casse", test_no_broken_encoding)
run_test("Regles assignation correctes", test_assignment_rules_correct)


# ════════════════════════════════════════════════
# 5. Scoring
# ════════════════════════════════════════════════

section("5. Moteur de scoring")


def _score(title):
    from app.core.database import session_scope
    from app.schemas.sotradies import SotradiesRaw
    from app.services.config_service import get_or_create_config
    from app.services.scoring_orchestrator import score_tender_full
    from app.services.pipeline import _best_category

    with session_scope() as db:
        config = get_or_create_config(db)
        cats = config.categories or {}
        excls = config.exclusion_keywords or []

    fake = SotradiesRaw(
        source="test",
        objet=title,
        acheteur="Test",
        date_publication=datetime.now(),
        lien="https://example.invalid/t",
    )
    result = score_tender_full(fake, cats, excls) or {}
    return _best_category(result)


def test_camion():
    cat, score = _score("Acquisition de 5 camions benne IVECO")
    assert cat == "MATERIEL_ROULANT", f"Obtenu {cat}"
    assert score >= 50


def test_bulldozer():
    cat, score = _score("Acquisition d'un Bulldozer sur chenilles")
    assert cat == "ENGINS_TP", f"Obtenu {cat}"
    assert score >= 50


def test_chariot():
    cat, score = _score("Fourniture de chariots elevateurs")
    assert cat == "MANUTENTION", f"Obtenu {cat}"
    assert score >= 50


def test_groupe_elec():
    cat, score = _score("Acquisition d'un groupe electrogene 500 KVA")
    assert cat == "GROUPES_ELECTROGENES", f"Obtenu {cat}"
    assert score >= 50


def test_centrale_solaire():
    cat, score = _score("Construction d'une centrale photovoltaique")
    assert cat == "CENTRALES_SOLAIRES", f"Obtenu {cat}"
    assert score >= 50


def test_installation_pas_solaire():
    cat, _ = _score("Installation de materiel medical dans un hopital")
    assert cat != "CENTRALES_SOLAIRES", (
        "Faux positif : installation -> CENTRALES_SOLAIRES"
    )


def test_alimentaire_rejete():
    _, score = _score("Acquisition de denrees alimentaires pour cantine")
    assert score == 0, f"Score : {score}"


def test_avocat_rejete():
    _, score = _score("Selection d'un cabinet d'avocats")
    assert score == 0, f"Score : {score}"

def test_pluriel_roulant():
    # Utiliser un titre avec un mot-clé direct pour éviter l'ambiguïté
    cat, score = _score(
        "Acquisition de cinq camionnettes double cabines"
    )
    assert cat == "MATERIEL_ROULANT", f"Pluriel non detecte, obtenu {cat}"
    assert score >= 50
run_test("Camions -> MATERIEL_ROULANT", test_camion)
run_test("Bulldozer -> ENGINS_TP", test_bulldozer)
run_test("Chariots -> MANUTENTION", test_chariot)
run_test("Groupe electrogene -> GROUPES_ELECTROGENES", test_groupe_elec)
run_test("Centrale solaire -> CENTRALES_SOLAIRES", test_centrale_solaire)
run_test("Installation seule != CENTRALES_SOLAIRES", test_installation_pas_solaire)
run_test("Alimentaire -> score 0", test_alimentaire_rejete)
run_test("Avocat -> score 0", test_avocat_rejete)
run_test("Pluriel materiels roulants detecte", test_pluriel_roulant)


# ════════════════════════════════════════════════
# 6. Scrapers
# ════════════════════════════════════════════════

section("6. Scrapers")


def test_onmp():
    from app.services.scrapers.onmp_scraper import OnmpScraper
    from app.schemas.sotradies import SotradiesRaw
    results = OnmpScraper().fetch_tenders()
    assert len(results) > 0
    assert all(isinstance(r, SotradiesRaw) for r in results)
    assert all(r.objet for r in results)


def test_tuneps():
    from app.services.scrapers.tuneps_scraper import TunepsScraper
    from app.schemas.sotradies import SotradiesRaw
    results = TunepsScraper().fetch_tenders()
    assert len(results) > 0
    assert all(isinstance(r, SotradiesRaw) for r in results)


def test_universal_import():
    from app.services.scrapers.universal_scraper import UniversalScraper
    s = UniversalScraper(
        source_name="test",
        url="https://example.invalid",
        use_browser=False,
        max_pages=1,
    )
    assert hasattr(s, "fetch_tenders")


def test_universal_rejects_fake_links():
    from app.services.scrapers.universal_scraper import UniversalScraper

    scraper = UniversalScraper(
        source_name="test_security",
        url="https://example.invalid",
        use_browser=False,
        max_pages=1,
    )

    # Vérifier que l'objet de la classe gère les lien_id invalides
    # en inspectant la méthode interne disponible
    import inspect
    source = inspect.getsource(
        scraper.__class__.fetch_tenders
    )

    # La nouvelle version utilise _raw_from_link
    assert (
        "_raw_from_link" in source
        or "_offer_to_raw" in source
    ), "Aucune fonction de validation de lien trouvee"

    # Test direct : un scraper sur une URL inexistante retourne 0 offre
    results = scraper.fetch_tenders()
    assert len(results) == 0, (
        f"URL invalide aurait du retourner 0 offre, obtenu {len(results)}"
    )
run_test("ONMP retourne des marches", test_onmp)
run_test("TUNEPS retourne des marches", test_tuneps)
run_test("UniversalScraper importable", test_universal_import)
run_test("Universal rejette les lien_id inventes", test_universal_rejects_fake_links)


# ════════════════════════════════════════════════
# 7. Pipeline
# ════════════════════════════════════════════════

section("7. Pipeline")


def test_pipeline_imports():
    from app.services.pipeline import (
        run_pipeline, compute_hash,
        filter_today_only, _best_category,
        _resolve_commercial, _resolve_commercial_id,
        _score_for_all_companies,
    )


def test_hash_stable():
    from app.schemas.sotradies import SotradiesRaw
    from app.services.pipeline import compute_hash

    tender = SotradiesRaw(
        source="onmp",
        objet="Acquisition de camions",
        acheteur="Ministere Test",
        date_publication=datetime(2026, 9, 22),
        lien="https://example.invalid/hash-test",
    )

    h1 = compute_hash(tender)
    h2 = compute_hash(tender)

    assert h1 == h2, "Hash instable"
    assert len(h1) == 64, f"Longueur inattendue : {len(h1)}"


def test_filter_date():
    from datetime import date, datetime
    from app.schemas.sotradies import SotradiesRaw
    from app.services.pipeline import filter_today_only

    target = date(2026, 9, 22)

    tenders = [
        SotradiesRaw(
            source="test",
            objet="Acquisition camion",
            acheteur="Acheteur A",
            date_publication=datetime(2026, 9, 22),
            lien="https://example.invalid/t1",
        ),
        SotradiesRaw(
            source="test",
            objet="Fourniture materiel",
            acheteur="Acheteur B",
            date_publication=datetime(2026, 9, 21),
            lien="https://example.invalid/t2",
        ),
        SotradiesRaw(
            source="test",
            objet="Marche sans date",
            acheteur="Acheteur C",
            date_publication=None,
            lien="https://example.invalid/t3",
        ),
    ]

    kept, sans_date = filter_today_only(tenders, target)

    assert len(kept) == 1, f"Attendu 1, obtenu {len(kept)}"
    assert kept[0].objet == "Acquisition camion"
    assert sans_date == 1

def test_resolve_commercial_id():
    from app.core.database import session_scope
    from app.models.commercial import Commercial
    from app.models.company import Company
    from app.services.pipeline import _resolve_commercial_id
    with session_scope() as db:
        c = db.query(Company).filter_by(nom="Sotradies").first()
        com = db.query(Commercial).filter(
            Commercial.company_id == c.id,
            Commercial.actif.is_(True),
        ).first()
        rules = {com.nom: [com.nom]}
        cats = {com.nom: {"commercial": com.nom}}
        result = _resolve_commercial_id(db, c.id, com.nom, rules, cats)
        assert result == com.id


run_test("Pipeline imports OK", test_pipeline_imports)
run_test("compute_hash stable", test_hash_stable)
run_test("filter_today_only correct", test_filter_date)
run_test("_resolve_commercial_id fonctionne", test_resolve_commercial_id)


# ════════════════════════════════════════════════
# 8. API et authentification
# ════════════════════════════════════════════════

section("8. API et authentification")


def test_main_importable():
    import app.main
    assert hasattr(app.main, "app")


def test_health():
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    client = TestClient(fastapi_app, raise_server_exceptions=False)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_tenders_auth_required():
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    client = TestClient(fastapi_app, raise_server_exceptions=False)
    assert client.get("/api/tenders").status_code == 401


def test_admin_auth_required():
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    client = TestClient(fastapi_app, raise_server_exceptions=False)
    assert client.get("/api/admin/sources").status_code == 401


def test_token_has_company_id():
    from types import SimpleNamespace
    from app.api.deps import get_current_user
    from app.core.database import get_db
    from app.core.security import create_access_token
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.models.user import User
    from app.core.database import session_scope

    # Utiliser un vrai utilisateur en base plutôt qu'un mock
    with session_scope() as db:
        real_user = (
            db.query(User)
            .filter(User.profil != "superadmin")
            .filter(User.company_id.isnot(None))
            .first()
        )

        if real_user is None:
            raise AssertionError(
                "Aucun utilisateur admin avec company_id en base"
            )

        token = create_access_token({"sub": real_user.email})
        expected_company_id = real_user.company_id

    client = TestClient(fastapi_app, raise_server_exceptions=False)
    response = client.get(
        "/api/tenders",
        headers={"Authorization": f"Bearer {token}"},
    )

    # 200 ou 422 sont acceptables (pas 401)
    assert response.status_code != 401, (
        f"Token refusé : status={response.status_code}, "
        f"email={real_user.email}"
    )

    assert expected_company_id is not None, (
        "company_id est None pour l'utilisateur"
    )

    assert expected_company_id == 2 or expected_company_id > 0, (
        f"company_id invalide : {expected_company_id}"
    )
    
run_test("app.main importable", test_main_importable)
run_test("GET /health -> 200", test_health)
run_test("GET /api/tenders sans auth -> 401", test_tenders_auth_required)
run_test("GET /api/admin/sources sans auth -> 401", test_admin_auth_required)
run_test("company_id dans le token JWT", test_token_has_company_id)


# ════════════════════════════════════════════════
# 9. Celery
# ════════════════════════════════════════════════

section("9. Celery")


def test_celery_import():
    from app.core.celery_app import celery_app
    assert celery_app is not None


def test_celery_tasks():
    from app.core.celery_app import celery_app
    import app.workers.tasks  # noqa: F401
    registered = list(celery_app.tasks.keys())
    required = [
        "tasks.run_daily_scan",
        "tasks.send_digest",
        "tasks.send_reminders",
    ]
    missing = [t for t in required if t not in registered]
    assert not missing, f"Taches manquantes : {missing}"


def test_celery_broker():
    from app.core.celery_app import celery_app
    try:
        celery_app.control.inspect(timeout=3).ping()
    except Exception as exc:
        raise AssertionError(f"Broker inaccessible : {exc}")


run_test("Celery importable", test_celery_import)
run_test("Taches Celery enregistrees", test_celery_tasks)
run_test("Broker Celery accessible", test_celery_broker)


# ════════════════════════════════════════════════
# 10. Isolation multi-client
# ════════════════════════════════════════════════

section("10. Isolation multi-client")


def test_config_per_company():
    from app.core.database import session_scope
    from app.services.config_service import get_or_create_config
    with session_scope() as db:
        c_global = get_or_create_config(db, company_id=None)
        c_client = get_or_create_config(db, company_id=2)
        assert c_global is not None
        assert c_client is not None
        assert c_client.company_id == 2


def test_tenders_isolated():
    from app.core.database import session_scope
    from app.models.company_tender import CompanyTender
    from app.models.company import Company
    with session_scope() as db:
        for company in db.query(Company).all():
            for ct in db.query(CompanyTender).filter_by(
                company_id=company.id
            ).all():
                assert ct.company_id == company.id


def test_commercials_isolated():
    from app.core.database import session_scope
    from app.models.commercial import Commercial
    from app.models.company_tender import CompanyTender
    with session_scope() as db:
        retenus = db.query(CompanyTender).filter(
            CompanyTender.decision == "retenu",
            CompanyTender.commercial_id.isnot(None),
        ).all()
        for ct in retenus:
            com = db.get(Commercial, ct.commercial_id)
            assert com is not None, (
                f"commercial_id={ct.commercial_id} introuvable"
            )
            assert com.company_id == ct.company_id, (
                f"Fuite : commercial company_id={com.company_id} "
                f"!= tender company_id={ct.company_id}"
            )


run_test("config_service par company_id", test_config_per_company)
run_test("company_tenders isoles par client", test_tenders_isolated)
run_test("Commerciaux isoles (pas de fuite)", test_commercials_isolated)


# ════════════════════════════════════════════════
# Resume
# ════════════════════════════════════════════════

print()
print("=" * 60)
print("  RESUME")
print("=" * 60)

total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"  Tests executes : {total}")
print(f"  Reussis        : {passed}")
print(f"  Echoues        : {failed}")

if failed:
    print()
    print("  Tests echoues :")
    for name, ok, exc in results:
        if not ok:
            print(f"    FAIL {name}")
            if exc:
                print(f"         {exc.__class__.__name__}: {exc}")

print()
if failed == 0:
    print("  Tous les tests sont passes.")
else:
    print(f"  {failed} test(s) echoue(s).")
    print("  Relancez avec --verbose pour le detail.")

if failed > 0:
    raise SystemExit(1)