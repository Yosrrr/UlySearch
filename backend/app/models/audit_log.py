"""
Trace chaque action effectuée sur une fiche marché, par qui et quand.
Règle 7 : "Tout est audité."
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sotradies_id = Column(String(64), ForeignKey("sotradies.id"), nullable=False)
    utilisateur_email = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)
    # ex: "consultation" | "changement_statut" | "rappel_j3_envoye" | "rappel_j1_envoye"
    detail = Column(Text, nullable=True)
    date_action = Column(DateTime, default=datetime.utcnow, nullable=False)