"""
Cache Redis générique, utilisé pour deux besoins distincts :
  - éviter de re-scraper trop souvent les mêmes sources (pipeline.py)
  - accélérer les réponses de l'API /tenders (api/tenders.py)

Base Redis séparée (index 2) de celle utilisée par Celery (index 0),
pour ne jamais mélanger cache applicatif et file de tâches.
"""
import json

import redis

from app.core.config import settings

_redis_client = redis.Redis.from_url(settings.CACHE_REDIS_URL, decode_responses=True)


def cache_get(key: str):
    raw = _redis_client.get(key)
    return json.loads(raw) if raw is not None else None


def cache_set(key: str, value, ttl_seconds: int):
    _redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


def cache_delete_pattern(pattern: str):
    """Supprime toutes les clés correspondant à un motif (ex: 'tenders:list:*')."""
    for key in _redis_client.scan_iter(match=pattern):
        _redis_client.delete(key)