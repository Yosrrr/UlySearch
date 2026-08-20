from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.system_action_log import SystemActionLog
from app.api.deps import require_superadmin
from app.services import process_manager
from app.core.config import settings

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


def _require_process_control():
    if not settings.ALLOW_PROCESS_CONTROL:
        raise HTTPException(
            status_code=409,
            detail="Les workers sont gérés comme services séparés sur cette plateforme.",
        )


def _log_action(db: Session, user: dict, action: str):
    """La journalisation ne doit jamais faire échouer l'action elle-même
    (démarrer/arrêter un process a réussi même si son log d'audit rate)."""
    try:
        db.add(SystemActionLog(utilisateur_email=user["sub"], action=action))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[admin_system] Échec de la journalisation (action déjà exécutée) : {e}")


@router.get("/status")
def status(user=Depends(require_superadmin)):
    return process_manager.get_status()


@router.post("/worker/start")
def worker_start(db: Session = Depends(get_db), user=Depends(require_superadmin)):
    _require_process_control()
    result = process_manager.start_worker()
    _log_action(db, user, "start_worker")
    return result


@router.post("/worker/stop")
def worker_stop(db: Session = Depends(get_db), user=Depends(require_superadmin)):
    _require_process_control()
    result = process_manager.stop_worker()
    _log_action(db, user, "stop_worker")
    return result


@router.post("/beat/start")
def beat_start(db: Session = Depends(get_db), user=Depends(require_superadmin)):
    _require_process_control()
    result = process_manager.start_beat()
    _log_action(db, user, "start_beat")
    return result


@router.post("/beat/stop")
def beat_stop(db: Session = Depends(get_db), user=Depends(require_superadmin)):
    _require_process_control()
    result = process_manager.stop_beat()
    _log_action(db, user, "stop_beat")
    return result