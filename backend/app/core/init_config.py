"""Initialisation de la configuration par défaut au démarrage de l'application."""
from app.core.database import SessionLocal
from app.models.configuration import Configuration
from app.core.keywords import CATEGORIES, EXCLUSION_KEYWORDS


def init_default_configuration():
    """
    Crée une configuration par défaut si elle n'existe pas.
    Appelé au démarrage de l'application.
    """
    db = SessionLocal()
    
    # Vérifier si une configuration existe déjà
    existing_config = db.query(Configuration).first()
    if existing_config:
        db.close()
        return existing_config
    
    # Construire la configuration par défaut à partir de keywords.py
    default_categories = {}
    for cat_id, cat_data in CATEGORIES.items():
        default_categories[cat_id] = {
            "commercial": cat_data.get("commercial"),
            "marques": cat_data.get("marques", []),
            "keywords": cat_data.get("keywords", []),
        }
    
    # Construire les règles d'assignation par défaut
    default_assignment_rules = {}
    for cat_id, cat_data in CATEGORIES.items():
        if cat_data.get("commercial"):
            default_assignment_rules[cat_id] = [cat_data["commercial"]]
    
    # Construire les sources actives par défaut
    default_sources = {
        "tuneps": {"actif": True, "frequence": "daily"},
        "tunisie_appel_offre": {"actif": True, "frequence": "daily"},
        "observatoire_national": {"actif": False, "frequence": "daily"},
    }
    
    # Créer la configuration par défaut
    default_config = Configuration(
        score_decision_threshold=50,
        score_instant_alert_threshold=70,
        categories=default_categories,
        exclusion_keywords=EXCLUSION_KEYWORDS,
        active_sources=default_sources,
        assignment_rules=default_assignment_rules,
        notes="Configuration initiale générée au premier démarrage"
    )
    
    db.add(default_config)
    db.commit()
    db.refresh(default_config)
    db.close()
    
    return default_config
