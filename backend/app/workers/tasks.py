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


@celery_app.task(name="tasks.test_single_source")
def test_single_source(source_id: int):
    """Test de scraping d'une seule source (appelé depuis l'admin)."""
    from app.core.database import session_scope
    from app.models.scraping_source import ScrapingSource
    from app.services.scrapers.universal_scraper import UniversalScraper
    from datetime import datetime

    with session_scope() as db:
        source = db.query(ScrapingSource).filter_by(id=source_id).first()
        if not source:
            return {"error": f"Source {source_id} introuvable"}

        scraper = UniversalScraper(
            source_name=f"test_{source.id}",
            url=source.url,
            use_browser=source.use_browser or False,
            max_pages=1,  # 1 seule page pour le test
        )

        try:
            tenders = scraper.fetch_tenders()
            source.last_scraped = datetime.utcnow()
            source.last_result_count = len(tenders)
            source.last_error = None

            return {
                "source": source.nom,
                "url": source.url,
                "status": "success",
                "count": len(tenders),
                "apercu": [
                    {
                        "objet": t.objet[:100] if t.objet else None,
                        "acheteur": t.acheteur,
                        "reference": t.reference,
                    }
                    for t in tenders[:5]
                ],
            }
        except Exception as e:
            source.error_count = (source.error_count or 0) + 1
            source.last_error = str(e)[:500]
            return {"source": source.nom, "error": str(e)}