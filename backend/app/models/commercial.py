"""Modèle SQLAlchemy des commerciaux.

Les emails des commerciaux sont stockés en base de données, jamais dans le code.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


class Commercial(Base):
    __tablename__ = "commercials"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Doit correspondre exactement aux noms utilisés dans :
    # - configuration.categories[...].commercial
    # - configuration.assignment_rules
    nom = Column(String(255), nullable=False, unique=True)

    email = Column(String(255), nullable=False, unique=True)

    actif = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Commercial id={self.id} nom={self.nom!r} "
            f"email={self.email!r} actif={self.actif}>"
        )