# ============================================================
# app/models/scraping_source.py
# ============================================================

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, func,
)
from app.core.database import Base


class ScrapingSource(Base):
    __tablename__ = "scraping_sources"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    type = Column(String(50), default="universel")
    actif = Column(Boolean, default=True)
    use_browser = Column(Boolean, default=False)
    max_pages = Column(Integer, default=3)
    notes = Column(Text, nullable=True)

    # Suivi
    last_scraped = Column(DateTime, nullable=True)
    last_result_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())