"""Utilisateurs du dashboard."""

from sqlalchemy.orm import relationship

from app.core.database import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # COLONNE (clé étrangère vers companies)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email = Column(String(255), unique=True, nullable=False)
    nom = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    profil = Column(String(20), nullable=False, default="user")
    actif = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")

    # RELATION vers Company (via users.company_id)
    company = relationship(
        "Company",
        foreign_keys=[company_id],
        back_populates="users",
    )

    # RELATION vers Company dont cet user est owner (via companies.owner_id)
    owned_company = relationship(
        "Company",
        foreign_keys="Company.owner_id",
        back_populates="owner",
        uselist=False,
    )