import inspect
import app.api.tenders as tenders
import app.services.notifier as notifier


def test_retenu_n_est_plus_un_statut_client():
    assert "retenu" not in tenders.CLIENT_STATUTS


def test_repechage_modifie_la_decision():
    src = inspect.getsource(tenders.update_tender_status)
    assert 'match.decision = "retenu"' in src and 'match.feedback = "pertinent"' in src


def test_resume_quotidien_couvre_le_week_end():
    src = inspect.getsource(notifier.send_daily_digest)
    assert "timedelta(days=4)" in src and "pas_pertinent" in src
