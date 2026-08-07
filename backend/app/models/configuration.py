"""Paramètres de configuration du système (mots-clés, seuils, sources actives, assignation)."""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.core.database import Base


class Configuration(Base):
    __tablename__ = "configuration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ===== Seuils de pertinence (Layer 4) =====
    score_decision_threshold = Column(Integer, default=50, nullable=False)
    # Score minimum pour qu'un marché soit "retenu" (pourcentage, 0-100)
    
    score_instant_alert_threshold = Column(Integer, default=80, nullable=False)
    # Score pour déclencher une alerte instantanée (vs digest quotidien)
    
    # ===== Mots-clés et catégories (Layer 4, Tier 1) =====
    # Stockés en JSONB pour permettre modification dynamique sans redéploiement
    # Format: {
    #   "MATERIEL_ROULANT": {
    #       "commercial": "Ramzi Trabelsi",
    #       "marques": ["IVECO", "Otokar"],
    #       "keywords": ["camion", "camionnette", ...]
    #   },
    #   ...
    # }
    categories = Column(JSONB, nullable=False, default={})
    
    # Mots-clés d'exclusion (liste simple)
    exclusion_keywords = Column(JSONB, nullable=False, default=[])
    
    # ===== Sources de scraping actives (Layer 1) =====
    # Format: {
    #   "tuneps": {"actif": true, "frquence": "daily"},
    #   "tunisie_appel_offre": {"actif": true, "frequence": "daily"},
    #   "observatoire_national": {"actif": false, "frequence": "daily"}
    # }
    active_sources = Column(JSONB, nullable=False, default={})
    
    # ===== Assignation commerciale (Layer 7) =====
    # Format: {
    #   "MATERIEL_ROULANT": ["Ramzi Trabelsi"],
    #   "ENGINS_TP": ["Zied Hajji"],
    #   "MANUTENTION": ["Salah Gharbi"],
    #   ...
    # }
    assignment_rules = Column(JSONB, nullable=False, default={})
    
    # ===== Metadata =====
    derniere_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    modifie_par = Column(String(255), nullable=True)  # email de l'utilisateur
    notes = Column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Configuration id={self.id} seuil_decision={self.score_decision_threshold}%>"
