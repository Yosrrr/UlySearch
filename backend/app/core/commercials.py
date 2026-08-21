"""
Récupération des emails des commerciaux depuis la table `commercials`.

Aucun email commercial n'est codé en dur dans le code source.
"""
from sqlalchemy.orm import Session

from app.models.commercial import Commercial


def get_email_for_commercial(db: Session, commercial_name: str) -> str | None:
    """Retourne l'email actif du commercial, ou None s'il n'existe pas."""
    if not commercial_name:
        return None

    commercial = (
        db.query(Commercial)
        .filter(
            Commercial.nom == commercial_name,
            Commercial.actif.is_(True),
        )
        .first()
    )

    if not commercial:
        print(f"[commercials] ⚠️ Aucun commercial actif trouvé pour : {commercial_name!r}")
        return None

    return commercial.email


def get_all_active_commercials(db: Session) -> list[Commercial]:
    """Retourne tous les commerciaux actifs."""
    return (
        db.query(Commercial)
        .filter(Commercial.actif.is_(True))
        .order_by(Commercial.nom)
        .all()
    )