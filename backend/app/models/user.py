"""Utilisateurs du dashboard (5 comptes prévus — direction + commerciaux)."""
from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    nom = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    profil = Column(String(20), nullable=False, default="user")  # "admin" | "user" | "superadmin"
    actif = Column(Boolean, nullable=False, default=True)