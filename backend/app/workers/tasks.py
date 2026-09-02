"""Tâches Celery principales."""

import random

# Import explicite : permet d'enregistrer tasks.run_cleanup dans Celery.
# Celery autodiscover charge app.workers.tasks, pas automatiquement
# cleanup_tasks.py.
from app.workers import cleanup_tasks  # noqa: F401
from app.services.reporting import send_periodic_report 
# à adapter au vrai nom
from app.core.celery_app import celery_app
from app.services.notifier import (
    dispatch_new_tenders,
    send_daily_digest,
    send_reminders,
)
from app.services.pipeline import run_pipeline


@celery_app.task(name="tasks.kickoff_daily_scan")
def kickoff_daily_scan():
    delay_seconds = random.randint(0, 1800)
    print(f"[kickoff] Départ du scan matinal programmé dans {delay_seconds}s")
    run_daily_scan.apply_async(countdown=delay_seconds)


@celery_app.task(name="tasks.run_daily_scan")
def run_daily_scan():
    """Scraping + scoring, puis alertes instantanées."""
    summary = run_pipeline()
    dispatch_new_tenders()
    return summary


@celery_app.task(name="tasks.send_digest")
def send_digest():
    """Récapitulatif quotidien."""
    return send_daily_digest()


@celery_app.task(name="tasks.send_reminders")
def send_reminders_task():
    """Rappels J-3 et J-1 avant la date limite."""
    return send_reminders()



@celery_app.task(name="tasks.send_periodic_report")
def send_periodic_report_task():
    """Rapport périodique à la direction (Layer 9 du CdC)."""
    return send_periodic_report()

