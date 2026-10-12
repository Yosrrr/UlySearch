from datetime import date

from app.services import notifier


def test_digest_uses_utc_date_when_target_date_is_omitted(monkeypatch):
    expected = date(2026, 10, 12)

    class FakeDateTime:
        @classmethod
        def now(cls, _timezone):
            return type("Now", (), {"date": lambda self: expected})()

    monkeypatch.setattr(notifier, "datetime", FakeDateTime)

    # Le calcul de date est exécuté avant l'accès à la base et à l'envoi.
    # On vérifie le comportement via le helper isolé utilisé par le digest.
    assert notifier._digest_target_date(None) == expected


def test_digest_preserves_explicit_target_date():
    expected = date(2026, 10, 9)
    assert notifier._digest_target_date(expected) == expected
