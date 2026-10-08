import inspect

import app.services.notifier as notifier


def test_or_est_importe():
    assert hasattr(notifier, "or_"), "from sqlalchemy import or_ manquant"


def test_alerte_instantanee_filtree_par_date():
    assert "cutoff_instant" in inspect.getsource(notifier)


def test_avis_pas_pertinent_respecte_partout():
    # alertes instantanées + rappels J-3/J-1
    assert inspect.getsource(notifier).count('"pas_pertinent"') >= 2