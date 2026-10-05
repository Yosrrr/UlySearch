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

def _seed_dedicated_sources(db) -> None:
    """Crée les sources dédiées ONMP/TUNEPS si absentes (idempotent, par nom).

    Sans ces lignes, un déploiement neuf ne collecte rien : les connecteurs
    dédiés ne sont instanciés que si une ligne scraping_sources existe
    et qu'au moins une entreprise y est abonnée (F-029).
    """
    from app.models.scraping_source import ScrapingSource

    dedicated = [
        {"nom": "ONMP", "url": "https://www.marchespublics.gov.tn/"},
        {"nom": "TUNEPS", "url": "https://www.tuneps.tn/portail/offres"},
    ]
    created = 0
    for spec in dedicated:
        exists = (
            db.query(ScrapingSource)
            .filter(
                ScrapingSource.type == "dedie",
                ScrapingSource.nom.ilike(spec["nom"]),
            )
            .first()
        )
        if exists is None:
            db.add(ScrapingSource(
                nom=spec["nom"],
                type="dedie",
                url=spec["url"],
                actif=True,
                use_browser=False,
                max_pages=3,
            ))
            created += 1
            print(f"[bootstrap] Source dédiée créée : {spec['nom']}")
        else:
            print(f"[bootstrap] Source dédiée déjà présente : {exists.nom}")
    if created:
        db.commit()
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

        _seed_dedicated_sources(db)
        _warn_if_no_commercials(db)
        seed_demo_tenders(db)


if __name__ == "__main__":
    bootstrap()