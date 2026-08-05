from celery.schedules import crontab

from app.core.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "kickoff-scan-matinal": {
        "task": "tasks.kickoff_daily_scan",
        "schedule": crontab(minute=58, hour=6, day_of_week="1-5"),
    },
    "scan-repete-journee": {
        "task": "tasks.run_daily_scan",
        "schedule": crontab(minute="*/30", hour="7-18", day_of_week="1-5"),
    },
    "digest-quotidien-8h": {
        "task": "tasks.send_digest",
        "schedule": crontab(minute=0, hour=8, day_of_week="1-5"),
    },
}