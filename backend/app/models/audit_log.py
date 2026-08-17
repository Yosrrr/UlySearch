"""Trace chaque action effectuée sur une fiche marché, par qui et quand,
ainsi que les connexions au système."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sotradies_id = Column(String(64), ForeignKey("sotradies.id"), nullable=True)
    utilisateur_email = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)
    # ex: "connexion" | "consultation" | "changement_statut"
    detail = Column(Text, nullable=True)
    date_action = Column(DateTime, default=datetime.utcnow, nullable=False)