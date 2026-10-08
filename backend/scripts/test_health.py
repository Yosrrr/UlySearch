from fastapi.testclient import TestClient
from app.main import app


def test_une_seule_route_health():
    assert len([r for r in app.routes if getattr(r, "path", None) == "/health"]) == 1


def test_health_verifie_la_base():
    assert "database" in TestClient(app).get("/health").json()
