"""
Tâches de purge automatique.

Cahier des charges §1.4 :
- rétention des données : 1 an ;
- purge automatique.

Politique appliquée :
- pipeline_log :
  - événements intermédiaires > 30 jours ;
  - événements restants > 365 jours.
- raw dumps :
  - fichiers data/raw_scrapes/*.txt > 30 jours.
- sent_log / audit_log :
  - logs > 365 jours.
- sotradies :
  - marchés détectés > 365 jours.
"""

from datetime import datetime, timedelta, UTC
from pathlib import Path

from app.core.database import session_scope
from app.models.audit_log import AuditLog
from app.models.pipeline_log import PipelineLog
from app.models.sent_log import SentLog
from app.models.sotradies import Sotradies

try:
    from app.core.celery_app import celery_app
except ImportError:  # pragma: no cover
    celery_app = None


PIPELINE_DETAIL_TYPES = [
    "SCRAPE_STARTED",
    "SCRAPE_FINISHED",
    "FILTER_DATE_SUMMARY",
    "DUPLICATE_RUN",
    "DUPLICATE_DB",
    "DETAIL_FETCHED",
    "EXCLUDED_KEYWORD",
    "UPDATED_EXISTING",
    "SCORED",
    "ASSIGNED",
    "INSERTED",
]


def purge_pipeline_logs(
    keep_summary_days: int = 365,
    keep_detail_days: int = 30,
) -> None:
    """Purge les logs pipeline selon leur niveau d'importance."""
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_scope() as db:
        detail_cutoff = now - timedelta(days=keep_detail_days)

        deleted_detail = (
            db.query(PipelineLog)
            .filter(
                PipelineLog.event_type.in_(PIPELINE_DETAIL_TYPES),
                PipelineLog.created_at < detail_cutoff,
            )
            .delete(synchronize_session=False)
        )

        summary_cutoff = now - timedelta(days=keep_summary_days)

        deleted_old = (
            db.query(PipelineLog)
            .filter(PipelineLog.created_at < summary_cutoff)
            .delete(synchronize_session=False)
        )

        print(
            f"[cleanup] pipeline_log : {deleted_detail} événement(s) détail "
            f"purgé(s) (>{keep_detail_days}j), {deleted_old} ancien(s) "
            f"événement(s) purgé(s) (>{keep_summary_days}j)"
        )


def purge_raw_dumps(keep_days: int = 30) -> None:
    """Purge les fichiers .txt de data/raw_scrapes/ plus vieux que keep_days."""
    raw_dir = Path("data/raw_scrapes")

    if not raw_dir.exists():
        print("[cleanup] raw_dumps : dossier absent, rien à purger.")
        return

    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    deleted = 0

    for file_path in raw_dir.glob("*.txt"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff:
                file_path.unlink()
                deleted += 1
        except Exception as exc:
            print(f"[cleanup] Erreur suppression {file_path}: {exc}")

    print(f"[cleanup] raw_dumps : {deleted} fichier(s) purgé(s) (>{keep_days}j)")


def purge_old_logs(keep_days: int = 365) -> None:
    """
    Purge audit_log et sent_log de plus d'un an.

    Cette purge est indépendante de la purge des marchés.
    """
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
            f"[cleanup] audit_log : {deleted_audit} purgé(s), "
            f"sent_log : {deleted_sent} purgé(s) (>{keep_days}j)"
        )


def purge_old_tenders(keep_days: int = 365):
    """Purge les marchés > 1 an et leurs logs liés (CdC §1.4).

    Ordre :
    1. Récupérer les IDs des marchés à purger
    2. Supprimer les sent_log/audit_log qui les référencent (FK)
    3. Supprimer les marchés eux-mêmes
    """
    from sqlalchemy import select

    cutoff = datetime.utcnow() - timedelta(days=keep_days)

    with session_scope() as db:
        # 1. Sélectionne les IDs (select() explicite — pas de Subquery implicite)
        old_ids_stmt = (
            select(Sotradies.id)
            .where(Sotradies.date_detection < cutoff)
        )

        # 2. Purge les tables enfants (contraintes FK)
        deleted_sent = (
            db.query(SentLog)
            .filter(SentLog.sotradies_id.in_(old_ids_stmt))
            .delete(synchronize_session=False)
        )
        deleted_audit = (
            db.query(AuditLog)
            .filter(AuditLog.sotradies_id.in_(old_ids_stmt))
            .delete(synchronize_session=False)
        )

        # 3. Purge les marchés eux-mêmes
        deleted_tenders = (
            db.query(Sotradies)
            .filter(Sotradies.date_detection < cutoff)
            .delete(synchronize_session=False)
        )

        print(
            f"[cleanup] sotradies : {deleted_tenders} marché(s) purgé(s) "
            f"(>{keep_days}j), logs liés supprimés : "
            f"sent_log={deleted_sent}, audit_log={deleted_audit}"
        )


def run_all_cleanup() -> None:
    """Lance toutes les purges automatiques."""
    print("[cleanup] Début purge automatique...")

    purge_pipeline_logs()
    purge_raw_dumps()
    purge_old_logs()
    purge_old_tenders()

    print("[cleanup] Purge terminée.")


if celery_app:

    @celery_app.task(name="tasks.run_cleanup")
    def run_cleanup_task():
        run_all_cleanup()
        return {"status": "ok"}