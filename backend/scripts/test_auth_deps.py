from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.api.deps import get_current_user, AUTH_COOKIE_NAME
from app.core.security import create_access_token


class FakeQuery:
    def __init__(self, user):
        self.user = user
    def filter_by(self, **kw):
        return self
    def first(self):
        return self.user

class FakeDB:
    def __init__(self, user):
        self.user = user
    def query(self, model):
        return FakeQuery(self.user)

class FakeRequest:
    def __init__(self, cookie_token=None, header_token=None):
        self.cookies = {AUTH_COOKIE_NAME: cookie_token} if cookie_token else {}
        self.headers = {"Authorization": f"Bearer {header_token}"} if header_token else {}


def test_get_current_user_rejects_disabled_user():
    token = create_access_token({"sub": "t@t.com", "profil": "admin"})
    u = SimpleNamespace(email="t@t.com", nom="T", profil="admin", actif=False)
    with pytest.raises(HTTPException) as exc:
        get_current_user(request=FakeRequest(cookie_token=token), db=FakeDB(u))
    assert exc.value.status_code == 401


def test_get_current_user_refreshes_profile_from_db():
    token = create_access_token({"sub": "t@t.com", "profil": "user"})
    u = SimpleNamespace(email="t@t.com", nom="Admin", profil="superadmin", actif=True)
    payload = get_current_user(request=FakeRequest(cookie_token=token), db=FakeDB(u))
    assert payload["profil"] == "superadmin"


def test_get_current_user_accepts_bearer_header_fallback():
    token = create_access_token({"sub": "t@t.com", "profil": "user"})
    u = SimpleNamespace(email="t@t.com", nom="T", profil="user", actif=True)
    payload = get_current_user(request=FakeRequest(header_token=token), db=FakeDB(u))
    assert payload["sub"] == "t@t.com"


def test_get_current_user_rejects_missing_token():
    with pytest.raises(HTTPException) as exc:
        get_current_user(request=FakeRequest(), db=FakeDB(None))
    assert exc.value.status_code == 401