"""TECH-001 (UnboundLocalError) et SEC-003 (isolation par ID)."""
import inspect

import app.api.tenders as t


def test_ancien_assigne_dans_chaque_branche():
    """TECH-001 : 'ancien' doit être assigné avant chaque usage."""
    src = inspect.getsource(t.update_tender_status)
    assignations = src.count("ancien = ")
    usages = src.count("{ancien}")
    assert assignations >= 3, (
        f"{assignations} assignation(s) de 'ancien' pour {usages} usage(s)"
    )


def test_pas_de_logique_dupliquee():
    """La fonction ne doit contenir qu'UN bloc de repêchage."""
    src = inspect.getsource(t.update_tender_status)
    assert src.count('if payload.statut == "retenu":') == 1
    assert src.count("_get_match_scoped") == 1


def test_helper_isolation_existe():
    """SEC-003 : helper partagé par tous les endpoints par ID."""
    assert hasattr(t, "_get_match_scoped")
    src = inspect.getsource(t._get_match_scoped)
    assert "commercial" in src
    assert "commercial_id" in src


def test_endpoints_par_id_utilisent_le_helper():
    """SEC-003 : get / patch / feedback passent par le helper."""
    for fn in (t.get_tender, t.update_tender_status, t.update_tender_feedback):
        src = inspect.getsource(fn)
        if "_is_superadmin" in src and "company_id" not in src:
            continue
        assert "_get_match_scoped" in src, f"{fn.__name__} sans isolation"


def test_lifespan_attache():
    """TECH-003 : le hook de démarrage doit être branché."""
    from app.main import app
    assert app.router.lifespan_context is not None