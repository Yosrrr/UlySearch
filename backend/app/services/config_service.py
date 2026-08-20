"""Accès centralisé à la configuration runtime (table `configuration`),
utilisé par l'API d'administration ET par le pipeline/notifier.
Prend désormais une session en paramètre — ne crée plus la sienne."""
from sqlalchemy.orm import Session

from app.models.configuration import Configuration


def get_or_create_config(db: Session) -> Configuration:
    config = db.query(Configuration).first()
    if not config:
        config = Configuration(
            score_decision_threshold=50,
            score_instant_alert_threshold=70,
            categories={},
            exclusion_keywords=[],
            active_sources={},
            assignment_rules={}
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config