"""
Configuration centralisée du Rate Limiter (slowapi).
Utilisé par main.py et par les routers (auth, buyers, etc.).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],           # limite globale
    storage_uri=settings.CACHE_REDIS_URL,    # utilise bien CACHE_REDIS_URL
)