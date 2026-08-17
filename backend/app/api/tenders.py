# app/api/tenders.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.sotradies import Sotradies
from app.models.audit_log import AuditLog
from app.schemas.tender_out import TenderOut, to_tender_out
from app.api.deps import get_current_user
from app.services.export_service import tenders_to_excel, tenders_to_pdf

router = APIRouter(prefix="/tenders", tags=["tenders"])


class TenderStatusUpdate(BaseModel):
    statut: str  # "nouveau" | "retenu" | "sans_suite"


def _filtered_tenders(db, search, commercial, statut, categorie, score_min, include_rejected):
    query = db.query(Sotradies)

    if search:
        like = f"%{search}%"
        query = query.filter(Sotradies.objet.ilike(like) | Sotradies.acheteur.ilike(like))
    if commercial and commercial != "Tous":
        query = query.filter(Sotradies.commercial_assigne == commercial)
    if statut and statut != "Tous":
        query = query.filter(Sotradies.statut == statut)

    results = query.order_by(Sotradies.date_detection.desc()).all()
    out = [to_tender_out(t) for t in results]

    if score_min is not None:
        out = [t for t in out if t.score >= score_min]
    elif not include_rejected:
        out = [t for t in out if t.score > 0 or t.statut == "retenu"]

    if categorie and categorie != "Toutes":
        out = [t for t in out if (t.top_categorie or "") == categorie]

    return out


@router.get("", response_model=list[TenderOut])
def list_tenders(
    search: str | None = Query(None),
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False),
    user=Depends(get_current_user),
):
    db = SessionLocal()
    out = _filtered_tenders(db, search, commercial, statut, categorie, score_min, include_rejected)
    db.close()
    return out


# ⚠️ /export et /rejected AVANT /{tender_id}, sinon FastAPI les confond avec un id
@router.get("/export")
def export_tenders(
    format: str = Query(..., pattern="^(xlsx|pdf)$"),
    search: str | None = Query(None),
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False),
    user=Depends(get_current_user),
):
    db = SessionLocal()
    tenders = _filtered_tenders(db, search, commercial, statut, categorie, score_min, include_rejected)
    db.close()

    date_str = datetime.utcnow().strftime("%Y%m%d")
    if format == "xlsx":
        content = tenders_to_excel(tenders)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"marches-sotradies-{date_str}.xlsx"
    else:
        content = tenders_to_pdf(tenders)
        media_type = "application/pdf"
        filename = f"marches-sotradies-{date_str}.pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/rejected", response_model=list[TenderOut])
def list_rejected_tenders(user=Depends(get_current_user)):
    db = SessionLocal()
    results = db.query(Sotradies).order_by(Sotradies.date_detection.desc()).all()
    out = [to_tender_out(t) for t in results]
    db.close()
    return [t for t in out if t.score < settings.RELEVANCE_RETAIN_THRESHOLD and t.statut != "retenu"]


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, user=Depends(get_current_user)):
    db = SessionLocal()
    t = db.query(Sotradies).filter_by(id=tender_id).first()

    if not t:
        db.close()
        raise HTTPException(status_code=404, detail="Marché introuvable")

    result = to_tender_out(t)

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user["sub"],
        action="consultation",
        detail=None,
    ))
    db.commit()
    db.close()

    return result


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

    db.add(AuditLog(
        sotradies_id=t.id,
        utilisateur_email=user.get("sub", "inconnu"),
        action="changement_statut",
        detail=f"{ancien_statut} -> {payload.statut}",
    ))

    db.commit()
    db.refresh(t)
    result = to_tender_out(t)
    db.close()
    return result