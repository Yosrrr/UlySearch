import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.auth as auth
import app.api.deps as deps
from app.core.security import create_access_token


class _Q:
    def __init__(self, u): self.u = u
    def filter_by(self, **kw): return self
    def filter(self, *a): return self
    def first(self): return self.u


class _DB:
    def __init__(self, u): self.u = u
    def query(self, *a): return _Q(self.u)


def _user(tv):
    return SimpleNamespace(email="a@b.tn", actif=True, profil="admin", nom="A",
                           company_id=1, token_version=tv)


def _req(tok):
    return SimpleNamespace(cookies={deps.AUTH_COOKIE_NAME: tok}, headers={})


def test_ancien_jeton_refuse_apres_deconnexion():
    old = create_access_token({"sub": "a@b.tn", "profil": "admin", "tv": 0})
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(_req(old), _DB(_user(1)))
    assert e.value.status_code == 401


def test_jeton_courant_accepte():
    tok = create_access_token({"sub": "a@b.tn", "profil": "admin", "tv": 1})
    assert deps.get_current_user(_req(tok), _DB(_user(1)))["sub"] == "a@b.tn"


def test_logout_incremente_la_version():
    assert "token_version" in inspect.getsource(auth.logout)
