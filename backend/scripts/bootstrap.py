"""Initialise le schéma et le premier administrateur.

Les commerciaux sont gérés séparément via l'API admin
(POST /api/admin/commercials) ou directement en base — aucun email
n'est stocké dans le code, la configuration ou les variables
d'environnement (correctif de sécurité S4).
"""
import os
from datetime import datetime, timedelta

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.commercial import Commercial  # noqa: F401
from app.models.known_buyer import KnownBuyer  # noqa: F401
from app.models.sent_log import SentLog  # noqa: F401
from app.models.sotradies import Sotradies
from app.models.system_action_log import SystemActionLog  # noqa: F401
from app.models.user import User


DEMO_TENDERS = [
    # ... (inchangé)
]


def seed_demo_tenders(db) -> None:
    if os.getenv("SEED_DEMO_DATA", "false").lower() not in ("1", "true", "yes"):
        return
    # ... (inchangé)


def _warn_if_no_commercials(db) -> None:
    """Avertissement clair au premier déploiement, sans jamais suggérer
    un email par défaut. L'ajout des commerciaux se fait via l'API
    /api/admin/commercials après connexion superadmin.
    """
    count = db.query(Commercial).filter_by(actif=True).count()
    if count == 0:
        print(
            "[bootstrap] ⚠️ Table commercials vide. "
            "Ajoutez vos commerciaux via l'API /api/admin/commercials "
            "ou via l'écran d'administration après connexion. "
            "Sans commercial actif, aucune alerte email ne partira."
        )
    else:
        print(f"[bootstrap] Commercials actifs en base : {count}")


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)

    email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    name = os.getenv("INITIAL_ADMIN_NAME", "Administrateur SOTRADIES").strip()

    with SessionLocal() as db:
        if email or password:
            if not email or not password:
                raise RuntimeError(
                    "INITIAL_ADMIN_EMAIL et INITIAL_ADMIN_PASSWORD doivent être fournis ensemble"
                )
            if len(password) < 12:
                raise RuntimeError(
                    "INITIAL_ADMIN_PASSWORD doit contenir au moins 12 caractères"
                )
            user = db.query(User).filter_by(email=email).first()
            if user:
                print(f"Administrateur déjà présent : {email}")
            else:
                db.add(User(
                    email=email,
                    nom=name,
                    password_hash=hash_password(password),
                    profil="superadmin",
                ))
                db.commit()
                print(f"Administrateur créé : {email}")
        else:
            print("Schéma initialisé; aucun administrateur demandé.")

        _warn_if_no_commercials(db)
        seed_demo_tenders(db)


if __name__ == "__main__":
    bootstrap()