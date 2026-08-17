import random

from app.core.celery_app import celery_app
from app.services.pipeline import run_pipeline
from app.services.notifier import dispatch_new_tenders, send_daily_digest, send_reminders



@celery_app.task(name="tasks.kickoff_daily_scan")
def kickoff_daily_scan():
    delay_seconds = random.randint(0, 1800)
    print(f"[kickoff] Départ du scan matinal programmé dans {delay_seconds}s")
    run_daily_scan.apply_async(countdown=delay_seconds)


@celery_app.task(name="tasks.run_daily_scan")
def run_daily_scan():
    """Scraping + scoring, puis alerte immédiate pour tout ce qui dépasse 80%."""
    summary = run_pipeline()
    dispatch_new_tenders()
    return summary


@celery_app.task(name="tasks.send_digest")
def send_digest():
    """Récapitulatif quotidien, une seule fois par jour."""
    send_daily_digest()

@celery_app.task(name="tasks.send_reminders")
def send_reminders_task():
    """Rappels J-3 et J-1 avant la date limite, pour les marchés non traités."""
    return send_reminders()