"""Identifiants privés d'une source, propres à une entreprise."""

from datetime import datetime, UTC
from app.core.time_utils import now_naive
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class SourceAccount(Base):
    __tablename__ = "source_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_source_id = Column(
        Integer,
        ForeignKey("company_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    login = Column(String(255), nullable=False)
    password_encrypted = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False)
    updated_at = Column(
        DateTime, default=now_naive, onupdate=now_naive, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("company_source_id", name="uq_source_account_company_source"),
    )