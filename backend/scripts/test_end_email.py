"""
Envoi de mails de test SOTRADIES — digest vide, digest avec marchés, alerte, rappel.
Usage:
  python -m scripts.test_send_emails votre.email@domaine.com
"""
import sys
from datetime import datetime, timedelta

from app.core.templates import jinja_env
from app.services.mailer import send_email


class FakeTender:
    def __init__(self, **kwargs):
        self.objet = kwargs.get("objet", "Acquisition de camions benne")
        self.acheteur = kwargs.get("acheteur", "Municipalité de Test")
        self.source = kwargs.get("source", "onmp")
        self.lien = kwargs.get("lien", "https://example.com/ao/123")
        self.date_limite = kwargs.get(
            "date_limite", datetime.now() + timedelta(days=10)
        )
        self.categorie = kwargs.get("categorie", "MATERIEL_ROULANT")
        self.acheteur_connu = kwargs.get("acheteur_connu", "Oui")
        self.description_detaillee = kwargs.get(
            "description_detaillee",
            "Fourniture de 3 camions pour les services techniques municipaux.",
        )
        self.score_details = kwargs.get(
            "score_details",
            {"MATERIEL_ROULANT": {"score": 85, "methode": "ia_directe"}},
        )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_send_emails email@destinataire.com")
        sys.exit(1)

    to_email = sys.argv[1].strip()
    t1 = FakeTender(objet="Acquisition de camions benne")
    t2 = FakeTender(
        objet="Fourniture chariot élévateur",
        acheteur="STE Test SA",
        acheteur_connu="Non",
        categorie="MANUTENTION",
        score_details={"MANUTENTION": {"score": 72}},
    )

    tests = []

    # 1) Digest VIDE
    html = jinja_env.get_template("digest_email.html").render(
        tenders=[],
        commercial="Commercial Test",
    )
    tests.append(
        (
            "TEST 1/4 — Digest VIDE — Aucun marché à traiter",
            html,
        )
    )

    # 2) Digest AVEC marchés
    html = jinja_env.get_template("digest_email.html").render(
        tenders=[t1, t2],
        commercial="Commercial Test",
    )
    tests.append(
        (
            "TEST 2/4 — Digest AVEC 2 marchés",
            html,
        )
    )

    # 3) Alerte instantanée
    html = jinja_env.get_template("instant_alert_email.html").render(
        tender=t1,
        score=85,
    )
    tests.append(
        (
            "TEST 3/4 — Alerte instantanée (score 85%)",
            html,
        )
    )

    # 4) Rappel J-3
    html = jinja_env.get_template("reminder_email.html").render(
        tender=t1,
        jours_restants=3,
    )
    tests.append(
        (
            "TEST 4/4 — Rappel J-3",
            html,
        )
    )

    print(f"Envoi de {len(tests)} emails de test vers {to_email} ...\n")

    for subject, body in tests:
        ok = send_email(to_email, subject, body)
        status = "✅ OK" if ok else "❌ ÉCHEC"
        print(f"{status}  {subject}")

    print("\nTerminé. Vérifiez votre boîte mail (et les spams).")


if __name__ == "__main__":
    main()