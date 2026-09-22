"""Table des acheteurs publics déjà connus/clients de Sotradies (Layer 5)."""
from sqlalchemy import Column, ForeignKey, Integer, String, Text

from app.core.database import Base


class KnownBuyer(Base):
    __tablename__ = "known_buyers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    nom_acheteur = Column(String(500), nullable=False)
    variantes = Column(Text, nullable=True)  # séparées par ";"
    client_sotradies = Column(String(10), nullable=False, default="Non")  # "Oui" | "Non"
    notes = Column(Text, nullable=True)