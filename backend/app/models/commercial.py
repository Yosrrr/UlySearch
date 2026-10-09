"""Modèle SQLAlchemy des commerciaux.

Les emails des commerciaux sont stockés en base de données, jamais dans le code.
"""


from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.time_utils import now_naive

class Commercial(Base):
    __tablename__ = "commercials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # RETIRER unique=True sur nom et email :
    nom = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)

    actif = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime,
        default=now_naive,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=now_naive,
        onupdate=now_naive,
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="commercials",
    )

    __table_args__ = (
        # Unicité PAR client, plus globale :
        UniqueConstraint("company_id", "nom", name="uq_commercial_company_nom"),
        UniqueConstraint("company_id", "email", name="uq_commercial_company_email"),
    )
    def __repr__(self) -> str:
        return (
            f"<Commercial id={self.id} nom={self.nom!r} "
            f"email={self.email!r} actif={self.actif}>"
        )