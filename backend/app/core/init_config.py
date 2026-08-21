"""Initialisation de la configuration par défaut au démarrage de l'application.

⚠️ keywords.py sert UNIQUEMENT de seed au premier démarrage.
Le runtime (pipeline, scoring, IA) lit exclusivement la table Configuration.
"""
from app.core.database import session_scope
from app.models.configuration import Configuration
from app.core.keywords import CATEGORIES, EXCLUSION_KEYWORDS


def init_default_configuration():
    """Crée une configuration par défaut si elle n'existe pas."""
    with session_scope() as db:
        existing_config = db.query(Configuration).first()
        if existing_config:
            return existing_config

        default_categories = {
            cat_id: {
                "commercial": cat_data.get("commercial"),
                "marques": cat_data.get("marques", []),
                "keywords": cat_data.get("keywords", []),
            }
            for cat_id, cat_data in CATEGORIES.items()
        }

        default_assignment_rules = {
            cat_id: [cat_data["commercial"]]
            for cat_id, cat_data in CATEGORIES.items()
            if cat_data.get("commercial")
        }

        default_sources = {
            "onmp": {"actif": True, "frequence": "daily"},
            "appeloffres": {"actif": True, "frequence": "daily"},
            "tuneps": {"actif": False, "frequence": "daily"},
        }

        default_config = Configuration(
            score_decision_threshold=50,
            score_instant_alert_threshold=70,
            categories=default_categories,
            exclusion_keywords=list(EXCLUSION_KEYWORDS),
            active_sources=default_sources,
            assignment_rules=default_assignment_rules,
            notes="Configuration initiale générée au premier démarrage",
        )
        db.add(default_config)
        db.flush()
        db.refresh(default_config)
        return default_config