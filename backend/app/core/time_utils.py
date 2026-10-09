"""Horodatage UTC sans tzinfo — cohérent avec les colonnes DateTime naïves."""
from datetime import UTC, datetime


def now_naive() -> datetime:
    """UTC courant, sans timezone (F-034)."""
    return datetime.now(UTC).replace(tzinfo=None)