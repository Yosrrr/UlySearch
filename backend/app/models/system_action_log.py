"""Trace chaque action de contrôle système (start/stop Worker/Beat)."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from app.core.database import Base


class SystemActionLog(Base):
    __tablename__ = "system_action_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    utilisateur_email = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)  # "start_worker" | "stop_worker" | "start_beat" | "stop_beat"
    date_action = Column(DateTime, default=datetime.utcnow, nullable=False)