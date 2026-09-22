"""
Informations détaillées de l'entreprise cliente.

Séparé du modèle User pour garder l'authentification simple
et stocker les données métier à part.
"""

from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Identité ──
    nom = Column(String(255), nullable=False)
    forme_juridique = Column(String(50), nullable=True)
    matricule_fiscal = Column(String(50), nullable=True, unique=True)
    secteur_activite = Column(String(255), nullable=True)
    annee_creation = Column(Integer, nullable=True)
    tranche_effectif = Column(String(50), nullable=True)

    # ── Contact principal ──
    responsable_nom = Column(String(255), nullable=True)
    responsable_fonction = Column(String(255), nullable=True)
    telephone_fixe = Column(String(20), nullable=True)
    telephone_mobile = Column(String(20), nullable=True)
    site_web = Column(String(500), nullable=True)
    linkedin = Column(String(500), nullable=True)

    # ── Localisation ──
    adresse = Column(String(500), nullable=True)
    code_postal = Column(String(10), nullable=True)
    ville = Column(String(100), nullable=True)
    gouvernorat = Column(String(100), nullable=True)
    pays = Column(String(100), default="Tunisie")

    # ── Activité commerciale ──
    description_activite = Column(Text, nullable=True)
    produits_services = Column(Text, nullable=True)
    marques_representees = Column(JSONB, default=list)
    certifications = Column(JSONB, default=list)
    clients_cibles = Column(Text, nullable=True)
    zones_intervention = Column(JSONB, default=list)
    concurrents = Column(Text, nullable=True)
    tranche_ca = Column(String(50), nullable=True)

    # ── Veille souhaitée ──
    types_offres = Column(Text, nullable=True)
    budget_min_interet = Column(Float, nullable=True)
    budget_max_interet = Column(Float, nullable=True)
    sites_consultes = Column(Text, nullable=True)
    frequence_alertes = Column(String(50), default="quotidien")
    
    users = relationship(
    "User",
    back_populates="company",
    passive_deletes=True,
    )


    # ── Lien avec User ──
    owner_id = Column(
    Integer,
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,    # ← DOIT être nullable
    unique=True,
    )

    users = relationship(
        "User",
        foreign_keys="User.company_id",
        back_populates="company",
        passive_deletes=True,
    )

    owner = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="owned_company",
        post_update=True,
    )

   


    # ── Statut ──
    onboarding_complete = Column(Boolean, default=False)

    # ── Timestamps ──
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    configuration = relationship(
    "Configuration",
    back_populates="company",
    uselist=False,
    )

    commercials = relationship(
        "Commercial",
        foreign_keys="Commercial.company_id",
        back_populates="company",
    )

    source_links = relationship(
        "CompanySource",
        back_populates="company",
    )

    tender_matches = relationship(
        "CompanyTender",
        back_populates="company",
    )

    def build_ai_description(self) -> str:
        """Construit la description envoyée à l'IA pour l'onboarding."""
        parts = []
        if self.description_activite:
            parts.append("Activite : " + self.description_activite)
        if self.produits_services:
            parts.append("Produits/Services : " + self.produits_services)
        if self.marques_representees:
            parts.append("Marques : " + ", ".join(self.marques_representees))
        if self.clients_cibles:
            parts.append("Clients cibles : " + self.clients_cibles)
        if self.types_offres:
            parts.append("Types d offres : " + self.types_offres)
        if self.concurrents:
            parts.append("Concurrents : " + self.concurrents)
        if self.gouvernorat:
            parts.append("Region : " + self.gouvernorat)
        if self.secteur_activite:
            parts.append("Secteur : " + self.secteur_activite)
        return "\n".join(parts)

    def __repr__(self):
        return "<Company " + self.nom + ">"