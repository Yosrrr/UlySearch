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

router = APIRouter(prefix="/tenders", tags=["tenders"])

LIST_CACHE_TTL = 30  # secondes — aligné avec staleTime (30_000ms) du frontend


@router.get("", response_model=list[TenderOut])
def list_tenders(
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    search: str | None = Query(None),
    user=Depends(get_current_user),
):
    cache_key = f"tenders:list:{commercial}:{statut}:{categorie}:{score_min}:{search}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    db = SessionLocal()
    query = db.query(Sotradies)

    if commercial and commercial != "Tous":
        query = query.filter(Sotradies.commercial_assigne == commercial)
    if statut and statut != "Tous":
        query = query.filter(Sotradies.statut == statut)

    results = query.order_by(Sotradies.date_detection.desc()).all()
    db.close()

    out = [to_tender_out(t) for t in results]

    if score_min is not None:
        out = [t for t in out if t.score >= score_min]
    if categorie and categorie != "Toutes":
        out = [t for t in out if t.top_categorie == categorie]
    if search:
        s = search.lower()
        out = [t for t in out if s in (t.objet or "").lower() or s in (t.acheteur or "").lower()]

    cache_set(cache_key, [t.model_dump(mode="json") for t in out], LIST_CACHE_TTL)
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
        utilisateur_email=getattr(user, "email", "inconnu"),
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
    db.close()

    if not t:
        raise HTTPException(status_code=404, detail="Marché introuvable")

    return to_tender_out(t)
