from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, tenders, admin_system, admin_users

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(admin_system.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}