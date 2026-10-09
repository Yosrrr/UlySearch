"""Trace chaque action effectuée sur une fiche marché, par qui et quand,
ainsi que les connexions au système."""


from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from app.core.time_utils import now_naive

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sotradies_id = Column(String(64), ForeignKey("sotradies.id"), nullable=True)
    utilisateur_email = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)
    # ex: "connexion" | "consultation" | "changement_statut"
    detail = Column(Text, nullable=True)
    date_action = Column(DateTime, default=now_naive, nullable=False)