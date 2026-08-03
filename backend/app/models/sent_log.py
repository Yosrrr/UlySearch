"""Empêche qu'un même marché soit envoyé deux fois par email (Layer 8)."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from app.core.database import Base


class SentLog(Base):
    __tablename__ = "sent_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sotradies_id = Column(String(64), ForeignKey("sotradies.id"), nullable=False)
    commercial = Column(String(255), nullable=False)
    canal = Column(String(20), nullable=False)  # "instantane" | "digest"
    date_envoi = Column(DateTime, default=datetime.utcnow, nullable=False)