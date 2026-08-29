"""
Tâches de purge automatique (cahier des charges §1.4 : rétention 1 an).

- pipeline_log : purge des événements intermédiaires > 30 jours,
  conserve RUN_FINISHED et ERROR 1 an
- raw_dump : purge des fichiers .txt > 30 jours
- tenders/audit/sent_log : purge > 1 an
"""
from datetime import datetime, timedelta
from pathlib import Path

from app.core.database import session_scope
from app.models.pipeline_log import PipelineLog
from app.models.audit_log import AuditLog
from app.models.sent_log import SentLog


try:
    from app.core.celery_app import celery_app
except ImportError:
    celery_app = None


def purge_pipeline_logs(keep_summary_days: int = 365, keep_detail_days: int = 30):
    """Purge les logs pipeline selon leur type."""
    now = datetime.utcnow()

    with session_scope() as db:
        # Événements intermédiaires > 30 jours
        detail_cutoff = now - timedelta(days=keep_detail_days)
        detail_types = [
            "SCRAPE_STARTED", "SCRAPE_FINISHED", "FILTER_DATE_SUMMARY",
            "DUPLICATE_RUN", "DUPLICATE_DB", "DETAIL_FETCHED",
            "EXCLUDED_KEYWORD", "UPDATED_EXISTING",
        ]
        deleted_detail = (
            db.query(PipelineLog)
            .filter(
                PipelineLog.event_type.in_(detail_types),
                PipelineLog.created_at < detail_cutoff,
            )
            .delete(synchronize_session=False)
        )

        # Événements importants > 1 an
        summary_cutoff = now - timedelta(days=keep_summary_days)
        deleted_summary = (
            db.query(PipelineLog)
            .filter(PipelineLog.created_at < summary_cutoff)
            .delete(synchronize_session=False)
        )

        print(
            f"[cleanup] pipeline_log : {deleted_detail} détails purgés (>{keep_detail_days}j), "
            f"{deleted_summary} résumés purgés (>{keep_summary_days}j)"
        )


def purge_raw_dumps(keep_days: int = 30):
    """Purge les fichiers .txt de data/raw_scrapes/ plus vieux que keep_days."""
    raw_dir = Path("data/raw_scrapes")
    if not raw_dir.exists():
        return

    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    deleted = 0

    for f in raw_dir.glob("*.txt"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception as e:
            print(f"[cleanup] Erreur suppression {f}: {e}")

    print(f"[cleanup] raw_dumps : {deleted} fichiers purgés (>{keep_days}j)")


def purge_old_data(keep_days: int = 365):
    """Purge audit_log et sent_log > 1 an."""
    cutoff = datetime.utcnow() - timedelta(days=keep_days)

    with session_scope() as db:
        deleted_audit = (
            db.query(AuditLog)
            .filter(AuditLog.date_action < cutoff)
            .delete(synchronize_session=False)
        )
        deleted_sent = (
            db.query(SentLog)
            .filter(SentLog.date_envoi < cutoff)
            .delete(synchronize_session=False)
        )

        print(
            f"[cleanup] audit_log : {deleted_audit} purgés, "
            f"sent_log : {deleted_sent} purgés (>{keep_days}j)"
        )


def run_all_cleanup():
    """Lance toutes les purges."""
    print("[cleanup] Début purge automatique...")
    purge_pipeline_logs()
    purge_raw_dumps()
    purge_old_data()
    print("[cleanup] Purge terminée.")


if celery_app:
    @celery_app.task(name="tasks.run_cleanup")
    def run_cleanup_task():
        run_all_cleanup()