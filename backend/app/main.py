from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.buyers import router as buyers_router

from app.core.config import settings
from app.core.database import init_db
from app.core.init_config import init_default_configuration

# Importer tous les modèles pour les enregistrer dans Base.metadata
from app.models import user, sotradies, sent_log, audit_log, known_buyer, system_action_log, configuration
from app.api import auth, tenders, admin_system, admin_users, admin_config

app = FastAPI(title=settings.APP_NAME)

# Initialiser la base de données et la configuration au démarrage
@app.on_event("startup")
async def startup_event():
    init_db()  # Créer les tables
    init_default_configuration()  # Initialiser la configuration par défaut

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(admin_system.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(admin_config.router, prefix="/api")
app.include_router(buyers_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


# En production, le frontend Vite est servi par le même service que l'API.
# Les routes API sont enregistrées avant ce catch-all, elles restent prioritaires.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


if FRONTEND_DIST.is_dir():
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        candidate = (FRONTEND_DIST / full_path).resolve()
        if FRONTEND_DIST.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
