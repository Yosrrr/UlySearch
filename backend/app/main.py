# app/main.py
from fastapi import FastAPI

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.api.tenders import router as tenders_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME)

app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(tenders_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}