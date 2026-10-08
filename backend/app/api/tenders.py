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
from app.services.buyer_rematcher import rematch_all_tenders
from app.services.buyer_rematcher import rematch_company_tenders
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.commercial import Commercial
from app.models.company_tender import CompanyTender
from app.models.sotradies import Sotradies
from app.schemas.tender_out import (
    TenderOut,
    TenderListPage,
    TenderStatusUpdate,
    to_tender_out_from_match,
    to_tender_out_from_sotradies,
)
from app.services.export_service import tenders_to_excel, tenders_to_pdf


router = APIRouter(prefix="/tenders", tags=["tenders"])

# Statuts autorisés côté client (cycle commercial)
CLIENT_STATUTS = {"nouveau", "en_cours", "sans_suite", "gagne", "perdu"}
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
    user: dict,
    search: str | None,
    commercial: str | None,
    statut: str | None,
    categorie: str | None,
    score_min: int | None,
    include_rejected: bool,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[TenderOut], int]:
    """
    retourne (page_items, total_filtré).
    total = nombre après TOUS les filtres (SQL + Python).
    limit=None → pas de coupe (export).
    """
    query = (
        db.query(CompanyTender, Sotradies)
        .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
        .filter(CompanyTender.company_id == company_id)
    )

    # ── Isolation commercial ──
    if user.get("profil") == "commercial":
        moi = (
            db.query(Commercial)
            .filter(
                Commercial.company_id == company_id,
                Commercial.email == user.get("sub"),
                Commercial.actif.is_(True),
            )
            .one_or_none()
        )
        if moi is None:
            return [], 0
        query = query.filter(CompanyTender.commercial_id == moi.id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            Sotradies.objet.ilike(like) | Sotradies.acheteur.ilike(like)
        )

    if statut and statut != "Tous":
        if statut == "retenu":
            query = query.filter(CompanyTender.decision == "retenu")
        elif statut == "rejete":
            query = query.filter(CompanyTender.decision == "rejete")
        else:
            query = query.filter(CompanyTender.statut == statut)

    if not include_rejected and score_min is None and (not statut or statut == "Tous"):
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

    total = len(out)

    if offset < 0:
        offset = 0
    if limit is not None:
        out = out[offset : offset + limit]
    elif offset:
        out = out[offset:]

    return out, total


def _filtered_for_superadmin(
    db: Session,
    search: str | None,
    commercial: str | None,
    statut: str | None,
    categorie: str | None,
    score_min: int | None,
    include_rejected: bool,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[TenderOut], int]:
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
    elif not include_rejected:
        out = [t for t in out if t.score > 0 or t.statut == "retenu"]

    if categorie and categorie != "Toutes":
        out = [t for t in out if (t.top_categorie or "") == categorie]

    total = len(out)

    if offset < 0:
        offset = 0
    if limit is not None:
        out = out[offset : offset + limit]
    elif offset:
        out = out[offset:]

    return out, total


@router.get("", response_model=TenderListPage)
def list_tenders(
    search: str | None = Query(None),
    commercial: str | None = Query(None),
    statut: str | None = Query(None),
    categorie: str | None = Query(None),
    score_min: int | None = Query(None),
    include_rejected: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        items, total = _filtered_for_superadmin(
            db,
            search,
            commercial,
            statut,
            categorie,
            score_min,
            include_rejected,
            limit=limit,
            offset=offset,
        )
    else:
        company_id = _require_company_id(user)
        items, total = _filtered_for_client(
            db,
            company_id,
            user,
            search,
            commercial,
            statut,
            categorie,
            score_min,
            include_rejected,
            limit=limit,
            offset=offset,
        )

    return TenderListPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
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
    # Export : pas de petite page, plafond anti-OOM
    export_limit = 5000

    if _is_superadmin(user):
        tenders, _total = _filtered_for_superadmin(
            db,
            search,
            commercial,
            statut,
            categorie,
            score_min,
            include_rejected,
            limit=export_limit,
            offset=0,
        )
    else:
        company_id = _require_company_id(user)
        tenders, _total = _filtered_for_client(
            db,
            company_id,
            user,
            search,
            commercial,
            statut,
            categorie,
            score_min,
            include_rejected,
            limit=export_limit,
            offset=0,
        )

    date_str = datetime.now(UTC).replace(tzinfo=None).strftime("%Y%m%d")
    app_slug = (settings.APP_NAME or "marches").lower().replace(" ", "-")

    if format == "xlsx":
        content = tenders_to_excel(tenders)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
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

@router.get("/rejected", response_model=TenderListPage)
def list_rejected_tenders(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if _is_superadmin(user):
        results = (
            db.query(Sotradies)
            .order_by(Sotradies.date_detection.desc())
            .all()
        )
        out = [to_tender_out_from_sotradies(t) for t in results]
        threshold = getattr(settings, "RELEVANCE_RETAIN_THRESHOLD", 50)
        out = [
            t for t in out
            if t.score < threshold and t.statut != "retenu"
        ]
        total = len(out)
        items = out[offset : offset + limit]
        return TenderListPage(
            items=items, total=total, limit=limit, offset=offset
        )

    company_id = _require_company_id(user)
    query = (
        db.query(CompanyTender, Sotradies)
        .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
        .filter(
            CompanyTender.company_id == company_id,
            CompanyTender.decision == "rejete",
        )
    )

    if user.get("profil") == "commercial":
        moi = (
            db.query(Commercial)
            .filter(
                Commercial.company_id == company_id,
                Commercial.email == user.get("sub"),
                Commercial.actif.is_(True),
            )
            .one_or_none()
        )
        if moi is None:
            return TenderListPage(
                items=[], total=0, limit=limit, offset=offset
            )
        query = query.filter(CompanyTender.commercial_id == moi.id)

    rows = query.order_by(Sotradies.date_detection.desc()).all()
    full = [
        to_tender_out_from_match(
            m, t, _commercial_name(db, m.commercial_id)
        )
        for m, t in rows
    ]
    total = len(full)
    items = full[offset : offset + limit]
    return TenderListPage(
        items=items, total=total, limit=limit, offset=offset
    )



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
    now = datetime.now(UTC).replace(tzinfo=None)

    # Superadmin : vue brute Sotradies (comportement inchangé)
    if _is_superadmin(user):
        if payload.statut not in SUPERADMIN_STATUTS:
            raise HTTPException(status_code=400, detail="Statut invalide.")
        t = db.query(Sotradies).filter_by(id=tender_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Marché introuvable")
        ancien = t.statut
        t.statut = payload.statut
        t.date_derniere_action = now
        db.add(AuditLog(
            sotradies_id=t.id,
            utilisateur_email=user.get("sub", "inconnu"),
            action="changement_statut",
            detail=f"{ancien} -> {payload.statut}",
        ))
        db.commit()
        db.refresh(t)
        return to_tender_out_from_sotradies(t)

    # Client
    company_id = _require_company_id(user)
    match = (
        db.query(CompanyTender)
        .filter_by(company_id=company_id, tender_id=tender_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Marché introuvable")

    if payload.statut == "retenu":
        # Repêchage = décision humaine : change la DÉCISION.
        # feedback="pertinent" protège l'offre contre les recalculs automatiques.
        ancien = match.decision
        match.decision = "retenu"
        match.feedback = "pertinent"
        match.feedback_at = now
        if match.statut in (None, "sans_suite"):
            match.statut = "nouveau"  # reprend le cycle commercial
        details = dict(match.score_details or {})
        details["_repechage"] = {"date": now.isoformat(timespec="seconds"),
                                 "par": user.get("sub"), "ancienne_decision": ancien}
        match.score_details = details
        action, detail = "repechage", f"{ancien} -> retenu"
    else:
        if payload.statut not in CLIENT_STATUTS:
            raise HTTPException(400, detail="Statut invalide.")
        match.statut = payload.statut
        action, detail = "changement_statut", f"{ancien} -> {payload.statut}"

    tender = db.query(Sotradies).filter_by(id=tender_id).first()
    if tender:
        tender.date_derniere_action = now

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user.get("sub", "inconnu"),
        action=action,
        detail=detail,
    ))
    db.commit()
    db.refresh(match)
    return to_tender_out_from_match(match, tender, _commercial_name(db, match.commercial_id))
