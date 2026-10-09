"""Valide le rendu du rapport direction sans envoyer d'email."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.templates import jinja_env as env


def test_template_rapport_se_rend():
    html = env.get_template("periodic_report_email.html").render(
        periode="01/10/2026 — 08/10/2026",
        total_detectes=154,
        total_retenus=48,
        total_alertes=5,
        total_acheteurs_connus=12,
        par_commercial=[
            {"commercial": "Yosr Sb", "nombre": 20},
            {"commercial": "Non assigné", "nombre": 3},
        ],
        par_source=[
            {"source": "onmp", "nombre": 50},
            {"source": "tuneps", "nombre": 100},
        ],
    )
    assert "154" in html
    assert "Yosr Sb" in html
    assert "onmp" in html
    # Pas de variable Jinja non résolue
    assert "{{" not in html


def test_rapport_skip_sans_direction_email(monkeypatch):
    from app.core.config import settings
    from app.services import reporting

    monkeypatch.setattr(settings, "DIRECTION_EMAIL", "", raising=False)
    result = reporting.send_periodic_report(days=7)
    assert result["status"] == "skipped"


def test_rapport_envoi_simule(monkeypatch):
    """send_email mocké : vérifie le contenu réel depuis la base."""
    from app.core.config import settings
    from app.services import reporting

    captured = {}

    def fake_send_email(to, subject, html):
        captured["to"] = to
        captured["subject"] = subject
        captured["html"] = html
        return True

    monkeypatch.setattr(settings, "DIRECTION_EMAIL", "direction@test.tn", raising=False)
    monkeypatch.setattr(reporting, "send_email", fake_send_email)

    result = reporting.send_periodic_report(days=30)

    assert result["status"] == "sent"
    assert captured["to"] == "direction@test.tn"
    assert "Rapport hebdomadaire" in captured["subject"]
    assert "{{" not in captured["html"]

    # Sauvegarde pour inspection visuelle
    Path("data/rapport_test.html").write_text(captured["html"], encoding="utf-8")
    print("Rapport écrit : data/rapport_test.html")