# ============================================================
# app/schemas/registration.py
# ============================================================

from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class CommercialInput(BaseModel):
    nom: str = Field(..., min_length=2, max_length=255)
    email: EmailStr


class RegistrationRequest(BaseModel):
    """Schéma complet d'inscription."""

    # ── Identité ──
    nom_entreprise: str = Field(..., min_length=2, max_length=255)
    forme_juridique: Optional[str] = None
    matricule_fiscal: Optional[str] = None
    secteur_activite: Optional[str] = None
    annee_creation: Optional[int] = Field(None, ge=1900, le=2030)
    tranche_effectif: Optional[str] = None

    # ── Contact ──
    responsable_nom: str = Field(..., min_length=2, max_length=255)
    responsable_fonction: Optional[str] = None
    email: EmailStr
    telephone_fixe: Optional[str] = None
    telephone_mobile: Optional[str] = None
    site_web: Optional[str] = None
    linkedin: Optional[str] = None

    # ── Localisation ──
    adresse: Optional[str] = None
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    gouvernorat: Optional[str] = None
    pays: str = "Tunisie"

    # ── Activité ──
    description_activite: str = Field(..., min_length=10, max_length=3000)
    produits_services: Optional[str] = None
    marques: Optional[str] = None
    certifications: Optional[list[str]] = []
    clients_cibles: Optional[str] = None
    zones_intervention: Optional[list[str]] = []
    concurrents: Optional[str] = None
    tranche_ca: Optional[str] = None

    # ── Veille ──
    types_offres: str = Field(..., min_length=5, max_length=2000)
    budget_min_interet: Optional[float] = Field(None, ge=0)
    budget_max_interet: Optional[float] = Field(None, ge=0)
    sites_consultes: Optional[str] = None
    frequence_alertes: str = "quotidien"

    # ── Équipe ──
    commerciaux: list[CommercialInput] = Field(
        ..., min_length=1, max_length=20
    )

    # ── Sécurité ──
    mot_de_passe: str = Field(..., min_length=8, max_length=128)
    confirmer_mot_de_passe: str = Field(..., min_length=8, max_length=128)


# ── Listes de choix pour le frontend ──

FORMES_JURIDIQUES = [
    "SARL", "SA", "SUARL", "SNC", "SCS",
    "Auto-entrepreneur", "Société civile", "Autre",
]

TRANCHES_EFFECTIF = [
    "1-10", "11-50", "51-200", "201-500", "500+",
]

GOUVERNORATS = [
    "Ariana", "Béja", "Ben Arous", "Bizerte",
    "Gabès", "Gafsa", "Jendouba", "Kairouan",
    "Kasserine", "Kébili", "Le Kef", "Mahdia",
    "La Manouba", "Médenine", "Monastir", "Nabeul",
    "Sfax", "Sidi Bouzid", "Siliana", "Sousse",
    "Tataouine", "Tozeur", "Tunis", "Zaghouan",
]

TRANCHES_CA = [
    "< 100 000 TND",
    "100 000 - 500 000 TND",
    "500 000 - 1 000 000 TND",
    "1 000 000 - 5 000 000 TND",
    "5 000 000+ TND",
]

FREQUENCES_ALERTES = [
    {"value": "instantane", "label": "Instantanée (chaque offre pertinente)"},
    {"value": "quotidien", "label": "Quotidienne (digest du jour)"},
    {"value": "hebdomadaire", "label": "Hebdomadaire (résumé de la semaine)"},
]

SECTEURS = [
    "BTP / Travaux publics",
    "Matériel roulant / Transport",
    "Informatique / IT",
    "Équipements médicaux",
    "Fournitures de bureau",
    "Agroalimentaire",
    "Énergie / Électricité",
    "Télécommunications",
    "Formation / Consulting",
    "Sécurité / Gardiennage",
    "Nettoyage / Entretien",
    "Autre",
]