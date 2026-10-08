from types import SimpleNamespace

from app.services import buyer_matcher as bm


def _interdit():
    raise AssertionError("La base ne doit pas être interrogée ici")


def test_sans_company_id_aucune_recherche(monkeypatch):
    monkeypatch.setattr(bm, "SessionLocal", _interdit)
    assert bm.match_buyer("Société des Transports de Tunis") is None
    assert bm.match_buyer_detail("Société des Transports de Tunis") == (None, None)


def test_acheteur_non_precise_jamais_rapproche(monkeypatch):
    monkeypatch.setattr(bm, "SessionLocal", _interdit)
    assert bm.match_buyer("Non précisé", company_id=1) is None


def test_rapprochement_dans_la_liste_du_client():
    kb = SimpleNamespace(nom_acheteur="Commune de Sfax", variantes=None, client_sotradies="Oui")
    assert bm.find_matching_buyer("Commune de Sfax", [kb]) is kb
    assert bm.find_matching_buyer("Commune de Soukra", [kb]) is None