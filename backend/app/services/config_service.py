"""Accès centralisé à la configuration runtime (table `configuration`),
utilisé par l'API d'administration ET par le pipeline/notifier."""
from app.core.database import SessionLocal
from app.models.configuration import Configuration


def get_or_create_config() -> Configuration:
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration(
            score_decision_threshold=50,
            score_instant_alert_threshold=80,
            categories={},
            exclusion_keywords=[],
            active_sources={},
            assignment_rules={}
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    db.close()
    return config