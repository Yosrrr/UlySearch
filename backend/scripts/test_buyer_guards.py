import inspect
import re

from app.services import buyer_matcher as bm
from app.services import buyer_rematcher as br


def _interdit(*args, **kwargs):
    raise AssertionError("La base ne doit pas être interrogée ici")


def test_find_matching_buyer_ne_lit_jamais_la_base(monkeypatch):
    monkeypatch.setattr(bm, "SessionLocal", _interdit)
    assert bm.find_matching_buyer("STEG") is None
    assert bm.find_matching_buyer("STEG", []) is None


def test_rematcher_utilise_seulement_les_acheteurs_du_client():
    src = inspect.getsource(br.rematch_company_tenders)
    assert not re.search(r"\bcid\b", src), "variable cid non définie"
    assert "is_(None)" not in src, "acheteurs globaux mélangés au client"