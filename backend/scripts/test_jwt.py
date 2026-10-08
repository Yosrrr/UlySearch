import inspect

import jwt

import app.core.security as security
from app.core.config import settings


def test_jeton_cree_et_relu_avec_pyjwt():
    tok = security.create_access_token({"sub": "a@b.tn", "profil": "admin"})
    data = jwt.decode(tok, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    assert data["sub"] == "a@b.tn" and "exp" in data


def test_jeton_invalide_refuse():
    assert security.decode_access_token("pas.un.jeton") is None


def test_plus_de_python_jose():
    assert "jose" not in inspect.getsource(security)
