"""
API des marchés — multi-tenant.

- admin / user  : lit/écrit CompanyTender de LEUR company_id
- superadmin    : lit les offres brutes Sotradies (vue plateforme)
"""
from datetime import UTC, datetime
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.commercial import Commercial
from app.models.company_tender import CompanyTender
from app.models.sotradies import Sotradies
from app.schemas.tender_out import (
    TenderOut,
    TenderStatusUpdate,
    to_tender_out_from_match,
    to_tender_out_from_sotradies,
)
from app.services.export_service import tenders_to_excel, tenders_to_pdf

router = APIRouter(prefix="/tenders", tags=["tenders"])

# Statuts autorisés côté client (cycle commercial)
CLIENT_STATUTS = {"nouveau", "en_cours", "sans_suite", "gagne", "perdu", "retenu"}
# Statuts autorisés côté superadmin (vue brute legacy)
SUPERADMIN_STATUTS = {"nouveau", "retenu", "sans_suite"}


class TenderFeedbackUpdate(BaseModel):
    feedback: str


def _is_superadmin(user: dict) -> bool:
    return user.get("profil") == "superadmin"


def _require_company_id(user: dict) -> int:
    company_id = user.get("company_id")
    if company_id is None:
        raise HTTPException(
            status_code=403,
            detail="Compte non rattaché à une entreprise.",
        )
    return int(company_id)


def _commercial_name(db: Session, commercial_id: int | None) -> str | None:
    if commercial_id is None:
        return None
    c = db.query(Commercial).filter_by(id=commercial_id).first()
    return c.nom if c else None


def _filtered_for_client(
    db: Session,
    company_id: int,
    search: str | None,
    commercial: str | None,
    statut: str | None,
    categorie: str | None,
    score_min: int | None,
    include_rejected: bool,
    *,
    user: dict,
) -> list[TenderOut]:
    query = (
        db.query(CompanyTender, Sotradies)
        .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
        .filter(CompanyTender.company_id == company_id)
    )
    if user.get("profil") == "commercial":
        email_connecte = str(user.get("sub") or "").strip().lower()
        moi = (
            db.query(Commercial)
            .filter(
                Commercial.company_id == company_id,
                func.lower(Commercial.email) == email_connecte,
                Commercial.actif.is_(True),
            )
            .order_by(Commercial.id)
            .first()
        )
        if moi is None:
            return []
        query = query.filter(CompanyTender.commercial_id == moi.id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            Sotradies.objet.ilike(like) | Sotradies.acheteur.ilike(like)
        )

    if statut and statut != "Tous":
        # "retenu" côté UI client = decision moteur
        if statut == "retenu":
            query = query.filter(CompanyTender.decision == "retenu")
        elif statut == "rejete":
            query = query.filter(CompanyTender.decision == "rejete")
        else:
            query = query.filter(CompanyTender.statut == statut)

    if not include_rejected and score_min is None and (not statut or statut == "Tous"):
        # Par défaut : tout marché avec un score > 0
        # (score = 0 = exclusion ou aucun mot-clé → caché par défaut)
        query = query.filter(CompanyTender.score > 0)

    results = query.order_by(Sotradies.date_detection.desc()).all()

    out: list[TenderOut] = []
    for match, tender in results:
        commercial_nom = _commercial_name(db, match.commercial_id)

        if commercial and commercial != "Tous":
            if (commercial_nom or "") != commercial:
                continue

        item = to_tender_out_from_match(match, tender, commercial_nom)

        if score_min is not None and item.score < score_min:
            continue

        if categorie and categorie != "Toutes":
            if (item.top_categorie or "") != categorie:
                continue

        out.append(item)

    return out


def _filtered_for_superadmin(
    db: Session,
    search: str | None,
    commercial: str | None,
    statut: str | None,
    categorie: str | None,
    score_min: int | None,
    include_rejected: bool,
) -> list[TenderOut]:
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
    out = [to_tender_out_from_sotradies(t) for t in results]

    if score_min is not None:
        out = [t for t in out if t.score >= score_min]

    if categorie and categorie != "Toutes":
        out = [t for t in out if (t.top_categorie or "") == categorie]

    return out


@router.get("", response_model=list[TenderOut])
def list_tenders(
    statut: str | None = None,
    search: str | None = Query(None),
    commercial: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False),
    db: Session = Depends(get_db),
     user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        return _filtered_for_superadmin(
            db, search, commercial, statut, categorie, score_min, include_rejected
        )

    company_id = _require_company_id(user)
    return _filtered_for_client(
        db, company_id, search, commercial, statut, categorie, score_min, include_rejected,
        user=user,
    )

@router.get("/export")
def export_tenders(
    format: str = Query(..., pattern="^(xlsx|pdf)$"),
    search: str | None = Query(None),
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        tenders = _filtered_for_superadmin(
            db, search, commercial, statut, categorie, score_min, include_rejected
        )
    else:
        company_id = _require_company_id(user)
        tenders = _filtered_for_client(
            db, company_id, search, commercial, statut, categorie, score_min, include_rejected,
            user=user,
        )

    date_str = datetime.now(UTC).replace(tzinfo=None).strftime("%Y%m%d")
    app_slug = (settings.APP_NAME or "marches").lower().replace(" ", "-")

    if format == "xlsx":
        content = tenders_to_excel(tenders)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"marches-{app_slug}-{date_str}.xlsx"
    else:
        content = tenders_to_pdf(tenders)
        media_type = "application/pdf"
        filename = f"marches-{app_slug}-{date_str}.pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/rejected", response_model=list[TenderOut])
def list_rejected_tenders(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        results = db.query(Sotradies).order_by(Sotradies.date_detection.desc()).all()
        out = [to_tender_out_from_sotradies(t) for t in results]
        threshold = getattr(settings, "RELEVANCE_RETAIN_THRESHOLD", 50)
        return [
            t for t in out
            if t.score < threshold and t.statut != "retenu"
        ]

    company_id = _require_company_id(user)
    rows = (
        db.query(CompanyTender, Sotradies)
        .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
        .filter(
            CompanyTender.company_id == company_id,
            CompanyTender.decision == "rejete",
        )
        .order_by(Sotradies.date_detection.desc())
        .all()
    )
    return [
        to_tender_out_from_match(m, t, _commercial_name(db, m.commercial_id))
        for m, t in rows
    ]


@router.patch("/{tender_id}/feedback", response_model=TenderOut)
def update_tender_feedback(
    tender_id: str,
    payload: TenderFeedbackUpdate,
    db: Session = Depends(get_db),
     user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        raise HTTPException(status_code=403, detail="Le feedback est réservé aux clients.")
    if payload.feedback not in {"pertinent", "pas_pertinent"}:
        raise HTTPException(status_code=400, detail="Feedback invalide.")

    company_id = _require_company_id(user)
    row = (
        db.query(CompanyTender, Sotradies)
        .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
        .filter(
            CompanyTender.company_id == company_id,
            CompanyTender.tender_id == tender_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Marché introuvable")

    match, tender = row
    match.feedback = payload.feedback
    match.feedback_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user.get("sub", "inconnu"),
        action="feedback",
        detail=payload.feedback,
    ))
    db.commit()
    db.refresh(match)
    return to_tender_out_from_match(match, tender, _commercial_name(db, match.commercial_id))


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(
    tender_id: str,
    db: Session = Depends(get_db),
     user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        t = db.query(Sotradies).filter_by(id=tender_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Marché introuvable")
        result = to_tender_out_from_sotradies(t)
    else:
        company_id = _require_company_id(user)
        row = (
            db.query(CompanyTender, Sotradies)
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                CompanyTender.company_id == company_id,
                CompanyTender.tender_id == tender_id,
            )
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Marché introuvable")
        match, tender = row
        result = to_tender_out_from_match(
            match, tender, _commercial_name(db, match.commercial_id)
        )

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user.get("sub", "inconnu"),
        action="consultation",
        detail=None,
    ))
    db.commit()
    return result


@router.patch("/{tender_id}", response_model=TenderOut)
def update_tender_status(
    tender_id: str,
    payload: TenderStatusUpdate,
    db: Session = Depends(get_db),
     user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        if payload.statut not in SUPERADMIN_STATUTS:
            raise HTTPException(status_code=400, detail="Statut invalide.")
        t = db.query(Sotradies).filter_by(id=tender_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Marché introuvable")
        ancien = t.statut
        t.statut = payload.statut
        t.date_derniere_action = datetime.now(UTC).replace(tzinfo=None)
        db.add(AuditLog(
            sotradies_id=t.id,
            utilisateur_email=user.get("sub", "inconnu"),
            action="changement_statut",
            detail=f"{ancien} -> {payload.statut}",
        ))
        db.commit()
        db.refresh(t)
        return to_tender_out_from_sotradies(t)

    # Client : on modifie CompanyTender.statut uniquement
    if payload.statut not in CLIENT_STATUTS:
        raise HTTPException(status_code=400, detail="Statut invalide.")

    company_id = _require_company_id(user)
    match = (
        db.query(CompanyTender)
        .filter_by(company_id=company_id, tender_id=tender_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Marché introuvable")

    ancien = match.statut
    match.statut = payload.statut

    tender = db.query(Sotradies).filter_by(id=tender_id).first()
    if tender:
        tender.date_derniere_action = datetime.now(UTC).replace(tzinfo=None)

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user.get("sub", "inconnu"),
        action="changement_statut",
        detail=f"{ancien} -> {payload.statut}",
    ))
    db.commit()
    db.refresh(match)

    tender = db.query(Sotradies).filter_by(id=tender_id).first()
    return to_tender_out_from_match(
        match, tender, _commercial_name(db, match.commercial_id)
    )