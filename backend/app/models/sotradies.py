from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Date, Numeric
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class Sotradies(Base):
    __tablename__ = "sotradies"

    id = Column(String(64), primary_key=True)
    reference = Column(String(255), nullable=True)
    objet = Column(Text, nullable=False)
    acheteur = Column(String(500), nullable=False)
    categorie = Column(String(255), nullable=True)
    date_publication = Column(DateTime, nullable=True)
    date_limite = Column(DateTime, nullable=True)
    budget_estime = Column(Numeric(14, 2), nullable=True)
    source = Column(String(50), nullable=False)
    lien = Column(Text, nullable=False)
    date_detection = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_data = Column(JSONB, nullable=True)

    statut = Column(String(30), default="nouveau", nullable=False)
    commercial_assigne = Column(String(255), nullable=True)
    score_details = Column(JSONB, nullable=True)
    acheteur_connu = Column(String(10), nullable=True)  # "Oui" | "Non" | None
    date_derniere_action = Column(DateTime, nullable=True)
    rappel_j3_envoye = Column(DateTime, nullable=True)
    rappel_j1_envoye = Column(DateTime, nullable=True)

    description_detaillee = Column(Text, nullable=True)
    budget_detecte = Column(Numeric(14, 2), nullable=True)
    duree_execution = Column(String(50), nullable=True)
    montant_cautionnement = Column(Numeric(14, 2), nullable=True)

    # --- Nouveaux détails extraits par l'IA (Layer 6, complément) ---
    type_marche = Column(String(50), nullable=True)              # "Fournitures" | "Travaux" | "Services"
    procedure_passation = Column(String(150), nullable=True)     # ex: "Appel d'offres ouvert"
    region_execution = Column(String(150), nullable=True)
    date_debut_execution = Column(Date, nullable=True)
    date_ouverture_offres = Column(Date, nullable=True)
    lieu_ouverture_offres = Column(String(255), nullable=True)
    caractere_prix = Column(String(50), nullable=True)           # "Ferme" | "Révisable"

    def __repr__(self) -> str:
        return f"<Sotradies id={self.id} statut={self.statut} objet={self.objet[:40]!r}>"
    
    