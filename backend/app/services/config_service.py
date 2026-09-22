"""Accès centralisé à la configuration runtime (table `configuration`),
utilisé par l'API d'administration ET par le pipeline/notifier.

Prend une session en paramètre — ne crée pas la sienne.

⚠️ Le paramètre company_id est optionnel pour préserver la compatibilité
   V1 (mono-client). Une fois le backfill effectué, chaque client aura
   sa propre ligne dans `configuration` via ce company_id.
"""
from sqlalchemy.orm import Session

# Force l'enregistrement de tous les modèles et de leurs relations
# avant toute requête ORM, quel que soit le point d'entrée
# (script, test, pipeline, tâche Celery, API).
import app.models  # noqa: F401

from app.models.configuration import Configuration


def get_or_create_config(db: Session, company_id: int | None = None) -> Configuration:
    query = db.query(Configuration)

    if company_id is not None:
        query = query.filter(Configuration.company_id == company_id)

    config = query.first()

    if not config:
        config = Configuration(
            company_id=company_id,
            score_decision_threshold=50,
            score_instant_alert_threshold=70,
            categories={},
            exclusion_keywords=[],
            active_sources={},
            assignment_rules={},
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return config