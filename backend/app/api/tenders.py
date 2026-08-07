from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import SessionLocal
from app.models.sotradies import Sotradies
from app.schemas.tender_out import TenderOut, to_tender_out
from app.api.deps import get_current_user
from datetime import datetime
from pydantic import BaseModel
from app.models.audit_log import AuditLog
from app.core.config import settings
from app.core.cache import cache_get, cache_set
from app.models.audit_log import AuditLog
from app.schemas.tender_out import TenderStatusUpdate

router = APIRouter(prefix="/tenders", tags=["tenders"])

LIST_CACHE_TTL = 30  # secondes — aligné avec staleTime (30_000ms) du frontend


@router.get("", response_model=list[TenderOut])
def list_tenders(
    search: str | None = Query(None, description="Recherche libre sur l'objet ou l'acheteur"),
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False, description="Inclure les marchés hors périmètre SOTRADIES"),
    user=Depends(get_current_user),
):
    db = SessionLocal()
    query = db.query(Sotradies)

    if search:
        like = f"%{search}%"
        query = query.filter(
            Sotradies.objet.ilike(like) | Sotradies.acheteur.ilike(like)
        )
    if commercial and commercial != "Tous":
        query = query.filter(Sotradies.commercial_assigne == commercial)
    if statut and statut != "Tous":
        query = query.filter(Sotradies.statut == statut)

    results = query.order_by(Sotradies.date_detection.desc()).all()
    db.close()

    out = [to_tender_out(t) for t in results]

    if score_min is not None:
        # L'utilisateur a explicitement choisi un seuil (ex: filtre "≥ 80%")
        out = [t for t in out if t.score >= score_min]
    elif not include_rejected:
        # Comportement par défaut : ne montrer QUE les offres concernant
        # SOTRADIES, c'est-à-dire celles qui ont matché au moins une catégorie
        # métier (score > 0) — on garde aussi les marchés "retenus" manuellement.
        out = [t for t in out if t.score > 0 or t.statut == "retenu"]

    if categorie and categorie != "Toutes":
        out = [t for t in out if (t.top_categorie or "") == categorie]

    return out


class TenderStatusUpdate(BaseModel):
    statut: str  # "nouveau" | "retenu" | "sans_suite"


@router.patch("/{tender_id}", response_model=TenderOut)
def update_tender_status(tender_id: str, payload: TenderStatusUpdate, user=Depends(get_current_user)):
    if payload.statut not in ("nouveau", "retenu", "sans_suite"):
        raise HTTPException(status_code=400, detail="Statut invalide.")

    db = SessionLocal()
    t = db.query(Sotradies).filter_by(id=tender_id).first()
    if not t:
        db.close()
        raise HTTPException(status_code=404, detail="Marché introuvable")

    ancien_statut = t.statut
    t.statut = payload.statut
    t.date_derniere_action = datetime.utcnow()

    # Règle 7 : "Tout est audité" — trace qui a changé le statut, et quand
    db.add(AuditLog(
        sotradies_id=t.id,
        utilisateur_email=user.get("sub", "inconnu"),
        action="changement_statut",
        detail=f"{ancien_statut} -> {payload.statut}",
    ))

    db.commit()
    db.refresh(t)
    db.close()
    return to_tender_out(t)

@router.get("/rejected", response_model=list[TenderOut])
def list_rejected_tenders(user=Depends(get_current_user)):
    db = SessionLocal()
    results = db.query(Sotradies).order_by(Sotradies.date_detection.desc()).all()
    db.close()
    out = [to_tender_out(t) for t in results]
    return [
        t for t in out
        if t.score < settings.RELEVANCE_RETAIN_THRESHOLD and t.statut != "retenu"
    ]


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, user=Depends(get_current_user)):
    db = SessionLocal()
    t = db.query(Sotradies).filter_by(id=tender_id).first()

    if not t:
        db.close()
        raise HTTPException(status_code=404, detail="Marché introuvable")

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user["sub"],
        action="consultation",
        detail=None,
    ))
    db.commit()
    db.close()

    return to_tender_out(t)

@router.patch("/{tender_id}", response_model=TenderOut)
def update_tender_status(tender_id: str, payload: TenderStatusUpdate, user=Depends(get_current_user)):
    if payload.statut not in ("retenu", "sans_suite", "nouveau"):
        raise HTTPException(status_code=400, detail="Statut invalide")

    db = SessionLocal()
    t = db.query(Sotradies).filter_by(id=tender_id).first()
    if not t:
        db.close()
        raise HTTPException(status_code=404, detail="Marché introuvable")

    t.statut = payload.statut
    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user["sub"],
        action="changement_statut",
        detail=f"Nouveau statut : {payload.statut}",
    ))
    db.commit()
    db.refresh(t)
    db.close()

    return to_tender_out(t)
