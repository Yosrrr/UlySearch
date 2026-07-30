# app/models/tender.py
from sqlalchemy import Column, String, Text, DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class Tender(Base):
    __tablename__ = "sotradies"

    id = Column(String(64), primary_key=True)
    reference = Column(String(255))
    objet = Column(Text, nullable=False)
    acheteur = Column(String(500), nullable=False)
    categorie = Column(String(255))
    date_publication = Column(DateTime)
    date_limite = Column(DateTime)
    budget_estime = Column(Numeric(14, 2))
    source = Column(String(50), nullable=False)
    lien = Column(Text, nullable=False)
    date_detection = Column(DateTime, nullable=False)
    raw_data = Column(JSONB)
    statut = Column(String(30), nullable=False)
    commercial_assigne = Column(String(255))
    score_details = Column(JSONB)
    date_derniere_action = Column(DateTime)
    rappel_j3_envoye = Column(DateTime)
    rappel_j1_envoye = Column(DateTime)