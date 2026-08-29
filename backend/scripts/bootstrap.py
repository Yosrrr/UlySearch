"""Initialise le schéma, le premier administrateur et les données de démo."""
import os
from datetime import datetime, timedelta

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.known_buyer import KnownBuyer  # noqa: F401
from app.models.sent_log import SentLog  # noqa: F401
from app.models.sotradies import Sotradies
from app.models.system_action_log import SystemActionLog  # noqa: F401
from app.models.user import User


DEMO_TENDERS = [
    ("demo-camions-bennes", "DEMO-2026-001", "Acquisition de camions bennes pour la collecte municipale", "Commune de Sfax", "Voitures, camions et engins", "Ramzi Trabelsi", "MATERIEL_ROULANT", 92, ["camion", "benne"], "Oui"),
    ("demo-chariots-elevateurs", "DEMO-2026-002", "Fourniture de chariots élévateurs électriques", "Office de la Marine Marchande et des Ports", "Manutention", "Salah Gharbi", "MANUTENTION", 88, ["chariot élévateur", "manutention"], "Oui"),
    ("demo-chargeuses", "DEMO-2026-003", "Acquisition de deux chargeuses sur pneus", "Office National des Mines", "BTP et travaux publics", "Zied Hajji", "ENGINS_TP", 81, ["chargeuse", "engin TP"], "Non"),
    ("demo-groupes-electrogenes", "DEMO-2026-004", "Installation de groupes électrogènes de secours", "Hôpital Universitaire de Tunis", "Équipements électriques", None, "GROUPES_ELECTROGENES", 74, ["groupe électrogène"], "Non"),
    ("demo-autocars", "DEMO-2026-005", "Fourniture de trois autocars interurbains", "Société Régionale de Transport du Sahel", "Transport", "Ramzi Trabelsi", "MATERIEL_ROULANT", 67, ["autocar"], "Oui"),
]


def seed_demo_tenders(db) -> None:
    if os.getenv("SEED_DEMO_DATA", "false").lower() not in ("1", "true", "yes"):
        return

    now = datetime.utcnow()
    created = 0
    for index, item in enumerate(DEMO_TENDERS):
        tender_id, reference, objet, acheteur, categorie, commercial, score_category, score, keywords, known = item
        if db.query(Sotradies).filter_by(id=tender_id).first():
            continue
        db.add(Sotradies(
            id=tender_id,
            reference=reference,
            objet=objet,
            acheteur=acheteur,
            categorie=categorie,
            commercial_assigne=commercial,
            score_details={score_category: {"score": score, "matched_keywords": keywords}},
            acheteur_connu=known,
            date_publication=now - timedelta(days=index),
            date_limite=now + timedelta(days=10 + index * 3),
            date_detection=now - timedelta(hours=index * 2),
            source="demo",
            lien="https://www.marchespublics.gov.tn/fr/appels-doffres",
            statut="retenu" if index == 2 else "nouveau",
        ))
        created += 1
    db.commit()
    print(f"Données de démonstration créées : {created}")


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)

    email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    name = os.getenv("INITIAL_ADMIN_NAME", "Administrateur SOTRADIES").strip()

    with SessionLocal() as db:
        if email or password:
            if not email or not password:
                raise RuntimeError("INITIAL_ADMIN_EMAIL et INITIAL_ADMIN_PASSWORD doivent être fournis ensemble")
            if len(password) < 12:
                raise RuntimeError("INITIAL_ADMIN_PASSWORD doit contenir au moins 12 caractères")
            user = db.query(User).filter_by(email=email).first()
            if user:
                print(f"Administrateur déjà présent : {email}")
            else:
                db.add(User(email=email, nom=name, password_hash=hash_password(password), profil="admin"))
                db.commit()
                print(f"Administrateur créé : {email}")
        else:
            print("Schéma initialisé; aucun administrateur demandé.")

        seed_demo_tenders(db)


if __name__ == "__main__":
    bootstrap()