"""
Planning des tâches périodiques (Celery Beat).
"""
from celery.schedules import crontab

from app.core.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Amorce matinale à heure interne fixe -> départ réel aléatoire 07h00-07h30
    "kickoff-scan-matinal": {
        "task": "tasks.kickoff_daily_scan",
        "schedule": crontab(minute=58, hour=6, day_of_week="1-5"),
    },
    # Scans répétés dans la journée, pour la réactivité (offres d'hier
    # qui seraient apparues en retard sur un des sites)
    "scan-repete-journee": {
        "task": "tasks.run_daily_scan",
        "schedule": crontab(minute="*/30", hour="7-18", day_of_week="1-5"),
    },
    
   
}