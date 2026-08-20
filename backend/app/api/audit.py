from fastapi import APIRouter, Depends, Query, Response
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.sotradies import Sotradies
from app.schemas.audit import AuditLogOut
from app.api.deps import require_superadmin
from app.services.export_service import audit_log_to_excel, audit_log_to_pdf

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


def _filtered_audit_log(db, utilisateur_email, action, limit):
    query = db.query(AuditLog)

    if utilisateur_email:
        query = query.filter(AuditLog.utilisateur_email.ilike(f"%{utilisateur_email}%"))
    if action and action != "Toutes":
        query = query.filter(AuditLog.action == action)

    logs = query.order_by(AuditLog.date_action.desc()).limit(limit).all()

    tender_ids = {log.sotradies_id for log in logs if log.sotradies_id}
    tenders_map = {}
    if tender_ids:
        tenders = db.query(Sotradies.id, Sotradies.objet).filter(Sotradies.id.in_(tender_ids)).all()
        tenders_map = {t.id: t.objet for t in tenders}

    return [
        AuditLogOut(
            id=log.id,
            sotradies_id=log.sotradies_id,
            tender_objet=tenders_map.get(log.sotradies_id),
            utilisateur_email=log.utilisateur_email,
            action=log.action,
            detail=log.detail,
            date_action=log.date_action,
        )
        for log in logs
    ]


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    utilisateur_email: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    admin=Depends(require_superadmin),
):
    return _filtered_audit_log(db, utilisateur_email, action, limit)


@router.get("/export")
def export_audit_log(
    format: str = Query(..., pattern="^(xlsx|pdf)$"),
    utilisateur_email: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(1000, le=5000),
    db: Session = Depends(get_db),
    admin=Depends(require_superadmin),
):
    logs = _filtered_audit_log(db, utilisateur_email, action, limit)

    date_str = datetime.utcnow().strftime("%Y%m%d")
    if format == "xlsx":
        content = audit_log_to_excel(logs)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"audit-log-sotradies-{date_str}.xlsx"
    else:
        content = audit_log_to_pdf(logs)
        media_type = "application/pdf"
        filename = f"audit-log-sotradies-{date_str}.pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )