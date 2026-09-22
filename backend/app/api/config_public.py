"""Lecture seule de la configuration, accessible à tout compte connecté
(contrairement à /admin/config qui reste réservé superadmin) — utilisé
par le Dashboard pour afficher le vrai seuil configuré, à jour en base."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.config_service import get_or_create_config

router = APIRouter(prefix="/config", tags=["config-public"])


def _config_for_user(db: Session, user: dict):
    company_id = user.get("company_id")
    return get_or_create_config(
        db,
        company_id=None if user.get("profil") == "superadmin" else company_id,
    )


@router.get("/thresholds")
def get_thresholds(db: Session = Depends(get_db), user=Depends(get_current_user)):
    config = _config_for_user(db, user)
    return {
        "score_decision_threshold": config.score_decision_threshold,
        "score_instant_alert_threshold": config.score_instant_alert_threshold,
    }


@router.get("/categories")
def get_categories(db: Session = Depends(get_db), user=Depends(get_current_user)):
    config = _config_for_user(db, user)
    return [
        {
            "id": category_id,
            "label": data.get("label") or category_id.replace("_", " ").capitalize(),
            "commercial": data.get("commercial"),
        }
        for category_id, data in (config.categories or {}).items()
        if isinstance(data, dict)
    ]