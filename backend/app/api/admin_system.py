from fastapi import APIRouter, Depends

from app.core.database import SessionLocal
from app.models.system_action_log import SystemActionLog
from app.api.deps import require_admin
from app.services import process_manager

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


def _log_action(user: dict, action: str):
    db = SessionLocal()
    db.add(SystemActionLog(utilisateur_email=user["sub"], action=action))
    db.commit()
    db.close()


@router.get("/status")
def status(user=Depends(require_admin)):
    return process_manager.get_status()


@router.post("/worker/start")
def worker_start(user=Depends(require_admin)):
    result = process_manager.start_worker()
    _log_action(user, "start_worker")
    return result


@router.post("/worker/stop")
def worker_stop(user=Depends(require_admin)):
    result = process_manager.stop_worker()
    _log_action(user, "stop_worker")
    return result


@router.post("/beat/start")
def beat_start(user=Depends(require_admin)):
    result = process_manager.start_beat()
    _log_action(user, "start_beat")
    return result


@router.post("/beat/stop")
def beat_stop(user=Depends(require_admin)):
    result = process_manager.stop_beat()
    _log_action(user, "stop_beat")
    return result