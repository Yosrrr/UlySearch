"""Chargement explicite de tous les modules de tâches.

Celery.autodiscover_tasks() ne charge par convention que `tasks.py`,
pas les autres modules du même package. On force l'import ici pour
garantir l'enregistrement de toutes les tâches, y compris cleanup_tasks.
"""
from app.workers import tasks           # noqa: F401
from app.workers import cleanup_tasks   # noqa: F401