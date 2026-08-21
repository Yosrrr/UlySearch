"""
Point d'entrée FastAPI — Sotradies Veille & Scoring AO.

Correctifs intégrés :
- S14 : En-têtes de sécurité HTTP
- S6  : Rate limiting avec slowapi (via app/core/rate_limiter.py)
"""

from pathlib import Path


from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.rate_limiter import limiter
from app.core.config import settings
from slowapi import _rate_limit_exceeded_handler
from app.core.init_config import init_default_configuration
from app.api.audit import router as audit_router

# Import des modèles
from app.models import (  # noqa: F401
    audit_log,
    commercial,
    configuration,
    known_buyer,
    pipeline_log,  # ← ajouter
    sent_log,
    sotradies,
    system_action_log,
    user,
)

# Import des routers
from app.api import (
    auth, tenders, admin_system, admin_users, admin_config, config_public
)
from app.api.buyers import router as buyers_router


app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from app.models import (  # noqa: F401
    audit_log, configuration, known_buyer, sent_log,
    sotradies, system_action_log, user, commercial,   # ← ajout
)
# Middleware de sécurité HTTP (S14)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        if settings.ENV.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
     # Exécuter automatiquement les migrations au démarrage

    
    init_default_configuration()


# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(admin_system.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(admin_config.router, prefix="/api")
app.include_router(config_public.router, prefix="/api")
app.include_router(buyers_router, prefix="/api")
app.include_router(audit_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


# Serve frontend Vite en production
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        candidate = (FRONTEND_DIST / full_path).resolve()
        if FRONTEND_DIST.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")