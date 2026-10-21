"""Chargement explicite de tous les modules de tâches.

Les imports explicites ci-dessous garantissent l'enregistrement de toutes
les tâches, y compris celles de cleanup_tasks.
"""
from app.workers import tasks
from app.workers import cleanup_tasks

__all__ = ["tasks", "cleanup_tasks"]
