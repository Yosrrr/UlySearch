"""Lecture seule de la configuration, accessible à tout compte connecté
(contrairement à /admin/config qui reste réservé superadmin) — utilisé
par le Dashboard pour afficher le vrai seuil configuré, à jour en base."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.config_service import get_or_create_config

router = APIRouter(prefix="/config", tags=["config-public"])


@router.get("/thresholds")
def get_thresholds(db: Session = Depends(get_db), user=Depends(get_current_user)):
    config = get_or_create_config(db)
    return {
        "score_decision_threshold": config.score_decision_threshold,
        "score_instant_alert_threshold": config.score_instant_alert_threshold,
    }