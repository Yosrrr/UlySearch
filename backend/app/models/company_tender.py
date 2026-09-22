"""
Résultat du scoring d'une offre POUR un client donné.

La table `sotradies` reste l'offre brute globale, partagée entre
tous les clients. Cette table porte tout ce qui est propre au client :
score, catégorie, commercial assigné, décision, statut, rappels.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class CompanyTender(Base):
    __tablename__ = "company_tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tender_id = Column(
        String(64),
        ForeignKey("sotradies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    score = Column(Integer, default=0, nullable=False)
    categorie = Column(String(255), nullable=True)
    score_details = Column(JSONB, nullable=True)

    # Verdict du moteur de scoring : "retenu" | "rejete"
    decision = Column(String(20), default="rejete", nullable=False)

    # Cycle de vie commercial : "nouveau" | "en_cours" | "sans_suite"
    #   | "gagne" | "perdu"
    statut = Column(String(30), default="nouveau", nullable=False)

    commercial_id = Column(
        Integer,
        ForeignKey("commercials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    acheteur_connu = Column(String(10), nullable=True)

    rappel_j3_envoye = Column(DateTime, nullable=True)
    rappel_j1_envoye = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="tender_matches",
    )
    tender = relationship("Sotradies")
    commercial = relationship("Commercial")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "tender_id",
            name="uq_company_tender",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyTender company_id={self.company_id} "
            f"tender_id={self.tender_id} decision={self.decision}>"
        )