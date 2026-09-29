"""Instance Celery centrale et configuration de son planning."""

from celery import Celery

from app.core.config import settings
from app.core.scheduler import BEAT_SCHEDULE


celery_app = Celery(
    "sotradies_watch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Tunis",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule=BEAT_SCHEDULE,
)

celery_app.autodiscover_tasks(["app.workers"])