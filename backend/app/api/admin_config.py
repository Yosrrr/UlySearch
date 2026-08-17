"""API endpoints pour la gestion de la configuration (réservé superadmin)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime


from app.core.database import SessionLocal
from app.api.deps import require_superadmin
from app.models.configuration import Configuration

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


# ===== Schemas Pydantic =====

class ThresholdsUpdate(BaseModel):
    score_decision_threshold: Optional[int] = None  # 0-100
    score_instant_alert_threshold: Optional[int] = None  # 0-100


class CategoriesUpdate(BaseModel):
    categories: Dict[str, Any]  # {"MATERIEL_ROULANT": {...}, ...}


class ExclusionKeywordsUpdate(BaseModel):
    exclusion_keywords: List[str]


class SourcesUpdate(BaseModel):
    active_sources: Dict[str, Dict[str, Any]]  # {"tuneps": {"actif": true, ...}, ...}


class AssignmentRulesUpdate(BaseModel):
    assignment_rules: Dict[str, List[str]]  # {"MATERIEL_ROULANT": ["Ramzi Trabelsi"], ...}


class ConfigurationResponse(BaseModel):
    id: int
    score_decision_threshold: int
    score_instant_alert_threshold: int
    categories: Dict[str, Any]
    exclusion_keywords: List[str]
    active_sources: Dict[str, Dict[str, Any]]
    assignment_rules: Dict[str, List[str]]
    derniere_modification: datetime
    modifie_par: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


# ===== Helper functions =====

def get_or_create_config():
    """Récupère la configuration singleton, ou la crée avec les valeurs par défaut."""
    db = SessionLocal()
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
    db.close()
    return config


# ===== Endpoints =====

@router.get("")
def get_configuration(user: dict = Depends(require_superadmin)):
    """Récupère la configuration actuelle."""
    config = get_or_create_config()
    return ConfigurationResponse.from_orm(config)


@router.put("/thresholds")
def update_thresholds(
    payload: ThresholdsUpdate,
    user: dict = Depends(require_superadmin)
):
    """Met à jour les seuils de pertinence."""
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration()
        db.add(config)

    if payload.score_decision_threshold is not None:
        if not (0 <= payload.score_decision_threshold <= 100):
            db.close()
            raise HTTPException(status_code=400, detail="score_decision_threshold doit être entre 0 et 100")
        config.score_decision_threshold = payload.score_decision_threshold

    if payload.score_instant_alert_threshold is not None:
        if not (0 <= payload.score_instant_alert_threshold <= 100):
            db.close()
            raise HTTPException(status_code=400, detail="score_instant_alert_threshold doit être entre 0 et 100")
        config.score_instant_alert_threshold = payload.score_instant_alert_threshold

    config.derniere_modification = datetime.utcnow()
    config.modifie_par = user.get("sub")  # email de l'utilisateur

    db.commit()
    db.refresh(config)
    db.close()

    return ConfigurationResponse.from_orm(config)


@router.put("/categories")
def update_categories(
    payload: CategoriesUpdate,
    user: dict = Depends(require_superadmin)
):
    """Met à jour les catégories et leurs mots-clés."""
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration()
        db.add(config)

    config.categories = payload.categories
    config.derniere_modification = datetime.utcnow()
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    db.close()

    return ConfigurationResponse.from_orm(config)


@router.put("/exclusion-keywords")
def update_exclusion_keywords(
    payload: ExclusionKeywordsUpdate,
    user: dict = Depends(require_superadmin)
):
    """Met à jour la liste des mots-clés d'exclusion."""
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration()
        db.add(config)

    config.exclusion_keywords = payload.exclusion_keywords
    config.derniere_modification = datetime.utcnow()
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    db.close()

    return ConfigurationResponse.from_orm(config)


@router.put("/sources")
def update_sources(
    payload: SourcesUpdate,
    user: dict = Depends(require_superadmin)
):
    """Met à jour l'activation des sources de scraping."""
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration()
        db.add(config)

    config.active_sources = payload.active_sources
    config.derniere_modification = datetime.utcnow()
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    db.close()

    return ConfigurationResponse.from_orm(config)


@router.put("/assignment-rules")
def update_assignment_rules(
    payload: AssignmentRulesUpdate,
    user: dict = Depends(require_superadmin)
):
    """Met à jour les règles d'assignation commerciale."""
    db = SessionLocal()
    config = db.query(Configuration).first()
    if not config:
        config = Configuration()
        db.add(config)

    config.assignment_rules = payload.assignment_rules
    config.derniere_modification = datetime.utcnow()
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    db.close()

    return ConfigurationResponse.from_orm(config)
