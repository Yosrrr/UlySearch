"""
Point d'entrée FastAPI — Sotradies Veille & Scoring AO.

Correctifs intégrés :
- S6  : Rate limiting avec SlowAPI
- S8  : Authentification par cookie httpOnly
- S9  : Schéma géré par Alembic
- S14 : En-têtes HTTP de sécurité
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.init_config import init_default_configuration
from app.core.rate_limiter import limiter
from fastapi.responses import JSONResponse
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Modèles SQLAlchemy
# ---------------------------------------------------------------------------

# Ces imports enregistrent les modèles dans Base.metadata et permettent
# à SQLAlchemy de résoudre leurs relations.
from app.models import (  # noqa: F401
    audit_log,
    commercial,
    company,
    company_source,
    company_tender,
    configuration,
    known_buyer,
    pipeline_log,
    scraping_source,
    source_account,
    sent_log,
    sotradies,
    system_action_log,
    user,
)

# ---------------------------------------------------------------------------
# Routeurs API
# ---------------------------------------------------------------------------

from app.api import (   
    admin_config,
    admin_system,
    admin_users,
    auth,
    config_public,
    tenders,
)
from app.api.admin_ai_suggest import (   
    router as ai_suggest_router,
)
from app.api.admin_commercials import (   
    router as admin_commercials_router,
)
from app.api.admin_sources import (   
    router as admin_sources_router,
)
from contextlib import asynccontextmanager
from app.api.admin_companies import router as admin_companies_router
from app.api.audit import router as audit_router   
from app.api.buyers import router as buyers_router   
from app.api.registration import (   
    router as registration_router,
)
import app.models 
 
import logging

from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from starlette.exceptions import HTTPException as StarletteHTTPException 


# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------

_is_production = str(settings.ENV).lower() == "production"

app = FastAPI(
    title=settings.APP_NAME,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)


app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)
onboarding_logger = logging.getLogger("uvicorn.error")


def _is_public_onboarding(request) -> bool:
    return (
        request.url.path.rstrip("/")
        == "/api/admin/ai-suggest/public"
    )


@app.exception_handler(RequestValidationError)
async def log_request_validation_error(request, exc):
    """
    Affiche les champs refusés sans journaliser
    tout le formulaire, les cookies ou les mots de passe.
    """
    if _is_public_onboarding(request):
        for error in exc.errors():
            field = ".".join(
                str(part)
                for part in error.get("loc", ())
            )

            onboarding_logger.warning(
                "[ONBOARDING 422] champ=%s | type=%s | message=%s",
                field,
                error.get("type", ""),
                error.get("msg", ""),
            )

    # Conserve la réponse normale de FastAPI.
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(StarletteHTTPException)
async def log_http_error(request, exc):
    """
    Affiche aussi les refus explicites de generate_suggestion().
    """
    if _is_public_onboarding(request) and exc.status_code == 422:
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Refus métier : consulter le champ detail de la réponse."
        )

        onboarding_logger.warning(
            "[ONBOARDING 422] refus metier=%s",
            detail,
        )

    return await http_exception_handler(request, exc)


# ---------------------------------------------------------------------------
# En-têtes de sécurité
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Ajoute les en-têtes HTTP de sécurité sur toutes les réponses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=()"
        )

        if settings.ENV.lower() == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        return response


# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_default_configuration()
    yield


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(admin_system.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(admin_companies_router, prefix="/api")
app.include_router(admin_config.router, prefix="/api")
app.include_router(admin_commercials_router, prefix="/api")
app.include_router(config_public.router, prefix="/api")
app.include_router(buyers_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(ai_suggest_router, prefix="/api")
app.include_router(admin_sources_router, prefix="/api")
app.include_router(registration_router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Liveness + deps (DB, Redis). 200 si ok, 503 si degraded."""
    checks: dict = {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
    }

    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error:{type(exc).__name__}"
        checks["status"] = "degraded"

    try:
        import redis as _redis
        r = _redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error:{type(exc).__name__}"
        checks["status"] = "degraded"

    code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=code)


# ---------------------------------------------------------------------------
# Frontend Vite en production
# ---------------------------------------------------------------------------

FRONTEND_DIST = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "dist"
)


if FRONTEND_DIST.is_dir():

    @app.get(
        "/{full_path:path}",
        include_in_schema=False,
    )
    def serve_frontend(full_path: str):
        frontend_root = FRONTEND_DIST.resolve()
        candidate = (FRONTEND_DIST / full_path).resolve()

        if (
            frontend_root in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)

        return FileResponse(
            FRONTEND_DIST / "index.html"
        )