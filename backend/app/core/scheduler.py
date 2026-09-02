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
    "rappels-j3-j1-8h30": {
        "task": "tasks.send_reminders",
        "schedule": crontab(minute=30, hour=8, day_of_week="1-5"),
    },
    "purge-donnees-hebdomadaire": {
    "task": "tasks.run_cleanup",
    "schedule": crontab(minute=0, hour=3, day_of_week="0"),  # dimanche 3h du matin
    },
    "rapport-hebdo-direction": {
    "task": "tasks.send_periodic_report",
    "schedule": crontab(day_of_week=1, hour=8, minute=0),  # lundi 8h
    },
    "tasks.send_periodic_report": {
    "task": "tasks.send_periodic_report",
    "schedule": crontab(hour=8, minute=0, day_of_week="mon"),
},
    
}