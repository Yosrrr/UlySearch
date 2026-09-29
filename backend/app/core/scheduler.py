"""Définition unique du planning Celery."""

from celery.schedules import crontab


BEAT_SCHEDULE = {
    "scan-toutes-les-sources": {
        "task": "tasks.run_daily_scan",
        "schedule": crontab(
            minute="*/30",
            hour="7-18",
            day_of_week="*",
        ),
    },

    "digest-quotidien-8h": {
        "task": "tasks.send_digest",
        "schedule": crontab(
            minute=0,
            hour=8,
            day_of_week="1-5",
        ),
    },

    "rappels-j3-j1-8h30": {
        "task": "tasks.send_reminders",
        "schedule": crontab(
            minute=30,
            hour=8,
            day_of_week="1-5",
        ),
    },

    "purge-donnees-hebdomadaire": {
        "task": "tasks.run_cleanup",
        "schedule": crontab(
            minute=0,
            hour=3,
            day_of_week="sun",
        ),
    },

    "rapport-hebdo-direction": {
        "task": "tasks.send_periodic_report",
        "schedule": crontab(
            minute=0,
            hour=8,
            day_of_week="mon",
        ),
    },
}