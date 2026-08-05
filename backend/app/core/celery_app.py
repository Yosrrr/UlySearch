"""
Instance Celery centrale. Le broker (Redis) est OBLIGATOIRE pour que
Celery Beat et les Workers puissent communiquer.
"""
from celery import Celery

from app.core.config import settings

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
)

celery_app.autodiscover_tasks(["app.workers"])

from app.core import scheduler  # noqa: E402,F401 - enregistre celery_app.conf.beat_schedule