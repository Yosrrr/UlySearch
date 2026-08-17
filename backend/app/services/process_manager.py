import os
import subprocess
import sys
from pathlib import Path

import psutil

BACKEND_DIR = Path(__file__).resolve().parents[2]
RUN_DIR = BACKEND_DIR / "run"
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
        return int(pidfile.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _process_matches_celery(pid: int, expected_role: str) -> bool:
    try:
        proc = psutil.Process(pid)
        if not proc.is_running():
            return False
        cmdline = " ".join(proc.cmdline()).lower()
        if "celery" not in cmdline:
            return False
        if expected_role == "worker" and "worker" not in cmdline:
            return False
        if expected_role == "beat" and "beat" not in cmdline:
            return False
        return True
    except (psutil.Error, psutil.NoSuchProcess):
        return False


def _is_running(pid: int | None, expected_role: str | None = None) -> bool:
    if pid is None:
        return False
    try:
        if not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
        if not proc.is_running():
            return False
        if expected_role is None:
            return True
        return _process_matches_celery(pid, expected_role)
    except psutil.Error:
        return False


def get_status() -> dict:
    worker_pid = _read_pid(WORKER_PIDFILE)
    beat_pid = _read_pid(BEAT_PIDFILE)
    worker_running = _is_running(worker_pid, "worker")
    beat_running = _is_running(beat_pid, "beat")
    if worker_pid is not None and not worker_running:
        WORKER_PIDFILE.unlink(missing_ok=True)
    if beat_pid is not None and not beat_running:
        BEAT_PIDFILE.unlink(missing_ok=True)
    return {
        "worker": {"running": worker_running, "pid": worker_pid if worker_running else None},
        "beat": {"running": beat_running, "pid": beat_pid if beat_running else None},
    }


def start_worker() -> dict:
    if _is_running(_read_pid(WORKER_PIDFILE)):
        return {"already_running": True}

    log = open(WORKER_LOGFILE, "a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.core.celery_app",
            "worker",
            "--loglevel=INFO",
            "--pool=solo",
            f"--pidfile={WORKER_PIDFILE}",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log,
        stderr=log,
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

    log = open(BEAT_LOGFILE, "a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.core.celery_app",
            "beat",
            "--loglevel=INFO",
            f"--pidfile={BEAT_PIDFILE}",
            f"--schedule={BEAT_SCHEDULE_FILE}",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log,
        stderr=log,
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