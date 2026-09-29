"""API endpoints pour la gestion de la configuration (réservé superadmin)."""
from datetime import datetime, UTC
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin_or_superadmin
from app.models.configuration import Configuration
from app.models.commercial import Commercial
from app.models.company_source import CompanySource
from app.models.scraping_source import ScrapingSource
from app.services.config_service import get_or_create_config

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


def _config_for_user(db: Session, user: dict):
    return get_or_create_config(
        db,
        company_id=user.get("context_company_id"),
    )


def _commercial_names(db: Session, user: dict) -> dict[str, str] | None:
    company_id = user.get("context_company_id")
    if company_id is None:
        return None

    return {
        commercial.nom.casefold(): commercial.nom
        for commercial in db.query(Commercial).filter(
            Commercial.company_id == company_id,
            Commercial.actif.is_(True),
        ).all()
    }


def _normalize_commercial(value: Any, names: dict[str, str] | None) -> Any:
    if value in (None, "") or names is None:
        return value
    if not isinstance(value, str) or value.casefold() not in names:
        raise HTTPException(
            status_code=422,
            detail="Chaque assignation doit référencer un commercial actif de l'entreprise.",
        )
    return names[value.casefold()]


def _validate_categories(
    categories: Dict[str, Any],
    names: dict[str, str] | None,
) -> Dict[str, Any]:
    normalized = dict(categories)
    for category_id, category in normalized.items():
        if not isinstance(category, dict):
            continue
        category = dict(category)
        category["commercial"] = _normalize_commercial(
            category.get("commercial"), names
        )
        normalized[category_id] = category
    return normalized


def _validate_assignment_rules(
    rules: Dict[str, List[str]],
    names: dict[str, str] | None,
) -> Dict[str, List[str]]:
    if names is None:
        return rules
    return {
        category_id: [
            _normalize_commercial(commercial, names)
            for commercial in commercials
        ]
        for category_id, commercials in rules.items()
    }


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
    model_config = ConfigDict(from_attributes=True)

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

def _runtime_active_sources(db: Session, user: dict, config: Configuration):
    company_id = user.get("context_company_id")
    if company_id is None:
        return config.active_sources or {}

    rows = db.query(ScrapingSource, CompanySource).join(
        CompanySource,
        CompanySource.source_id == ScrapingSource.id,
    ).filter(CompanySource.company_id == company_id).all()
    return {
        source.nom.strip().lower(): {
            "actif": bool(link.actif and source.actif),
            "source_id": source.id,
            "type": source.type,
        }
        for source, link in rows
    }


def _configuration_response(db: Session, config: Configuration, user: dict):
    data = ConfigurationResponse.model_validate(config).model_dump()
    data["active_sources"] = _runtime_active_sources(db, user, config)
    return data


# ===== Endpoints =====

@router.get("")
def get_configuration(db: Session = Depends(get_db), user: dict = Depends(require_admin_or_superadmin)):
    """Récupère la configuration actuelle."""
    config = _config_for_user(db, user)
    return _configuration_response(db, config, user)


@router.put("/thresholds")
def update_thresholds(
    payload: ThresholdsUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_superadmin)
):
    """Met à jour les seuils de pertinence."""
    config = _config_for_user(db, user)

    if payload.score_decision_threshold is not None:
        if not (0 <= payload.score_decision_threshold <= 100):
            raise HTTPException(status_code=400, detail="score_decision_threshold doit être entre 0 et 100")
        config.score_decision_threshold = payload.score_decision_threshold

    if payload.score_instant_alert_threshold is not None:
        if not (0 <= payload.score_instant_alert_threshold <= 100):
            raise HTTPException(status_code=400, detail="score_instant_alert_threshold doit être entre 0 et 100")
        config.score_instant_alert_threshold = payload.score_instant_alert_threshold

    config.derniere_modification = datetime.now(UTC).replace(tzinfo=None)
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    return _configuration_response(db, config, user)


@router.put("/categories")
def update_categories(
    payload: CategoriesUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_superadmin)
):
    """Met à jour les catégories et leurs mots-clés."""
    config = _config_for_user(db, user)

    config.categories = _validate_categories(
        payload.categories,
        _commercial_names(db, user),
    )
    config.derniere_modification = datetime.now(UTC).replace(tzinfo=None)
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    return _configuration_response(db, config, user)


@router.put("/exclusion-keywords")
def update_exclusion_keywords(
    payload: ExclusionKeywordsUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_superadmin)
):
    """Met à jour la liste des mots-clés d'exclusion."""
    config = _config_for_user(db, user)

    config.exclusion_keywords = payload.exclusion_keywords
    config.derniere_modification = datetime.now(UTC).replace(tzinfo=None)
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    return _configuration_response(db, config, user)


@router.put("/sources")
def update_sources(
    payload: SourcesUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_superadmin)
):
    """Met à jour l'activation des sources de scraping."""
    config = _config_for_user(db, user)

    company_id = user.get("context_company_id")
    if company_id is not None:
        rows = db.query(ScrapingSource, CompanySource).join(
            CompanySource,
            CompanySource.source_id == ScrapingSource.id,
        ).filter(CompanySource.company_id == company_id).all()
        requested = {
            str(name).strip().lower(): bool(value.get("actif", False))
            for name, value in payload.active_sources.items()
            if isinstance(value, dict)
        }
        for source, link in rows:
            key = source.nom.strip().lower()
            if key in requested:
                link.actif = requested[key]
    else:
        # Compatibilité de la configuration globale historique.
        config.active_sources = payload.active_sources
    config.derniere_modification = datetime.now(UTC).replace(tzinfo=None)
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    return _configuration_response(db, config, user)


@router.put("/assignment-rules")
def update_assignment_rules(
    payload: AssignmentRulesUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_superadmin)
):
    """Met à jour les règles d'assignation commerciale."""
    config = _config_for_user(db, user)

    config.assignment_rules = _validate_assignment_rules(
        payload.assignment_rules,
        _commercial_names(db, user),
    )
    config.derniere_modification = datetime.now(UTC).replace(tzinfo=None)
    config.modifie_par = user.get("sub")

    db.commit()
    db.refresh(config)
    return _configuration_response(db, config, user)