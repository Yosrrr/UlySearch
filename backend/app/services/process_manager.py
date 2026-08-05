"""
Démarre, arrête et vérifie l'état des processus Celery Worker et Beat,
via des fichiers PID. Fonctionne aussi bien sur Windows (dev) que sur
Linux (serveur de production).

⚠️ Sécurité : les commandes lancées sont toujours FIXES (jamais construites
à partir d'une entrée utilisateur) — seul un compte "admin" authentifié
peut appeler ces fonctions (voir app/api/admin_system.py).
"""
import subprocess
import sys
from pathlib import Path

import psutil

RUN_DIR = Path("run")
RUN_DIR.mkdir(exist_ok=True)

WORKER_PIDFILE = RUN_DIR / "worker.pid"
WORKER_LOGFILE = RUN_DIR / "worker.log"
BEAT_PIDFILE = RUN_DIR / "beat.pid"
BEAT_LOGFILE = RUN_DIR / "beat.log"
BEAT_SCHEDULE_FILE = RUN_DIR / "celerybeat-schedule"


def _read_pid(pidfile: Path) -> int | None:
    if not pidfile.exists():
        return None
    try:
        return int(pidfile.read_text().strip())
    except (ValueError, OSError):
        return None


def _is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except psutil.Error:
        return False


def get_status() -> dict:
    worker_pid = _read_pid(WORKER_PIDFILE)
    beat_pid = _read_pid(BEAT_PIDFILE)
    return {
        "worker": {"running": _is_running(worker_pid), "pid": worker_pid},
        "beat": {"running": _is_running(beat_pid), "pid": beat_pid},
    }


def start_worker() -> dict:
    if _is_running(_read_pid(WORKER_PIDFILE)):
        return {"already_running": True}

    log = open(WORKER_LOGFILE, "a")
    subprocess.Popen(
        [
            sys.executable, "-m", "celery",
            "-A", "app.core.celery_app", "worker",
            "--loglevel=INFO", "--pool=solo",
            f"--pidfile={WORKER_PIDFILE}",
        ],
        stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    return {"started": True}


def stop_worker() -> dict:
    pid = _read_pid(WORKER_PIDFILE)
    if not _is_running(pid):
        return {"already_stopped": True}
    psutil.Process(pid).terminate()
    WORKER_PIDFILE.unlink(missing_ok=True)
    return {"stopped": True}


def start_beat() -> dict:
    if _is_running(_read_pid(BEAT_PIDFILE)):
        return {"already_running": True}

    log = open(BEAT_LOGFILE, "a")
    subprocess.Popen(
        [
            sys.executable, "-m", "celery",
            "-A", "app.core.celery_app", "beat",
            "--loglevel=INFO",
            f"--pidfile={BEAT_PIDFILE}",
            f"--schedule={BEAT_SCHEDULE_FILE}",
        ],
        stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    return {"started": True}


def stop_beat() -> dict:
    pid = _read_pid(BEAT_PIDFILE)
    if not _is_running(pid):
        return {"already_stopped": True}
    psutil.Process(pid).terminate()
    BEAT_PIDFILE.unlink(missing_ok=True)
    return {"stopped": True}