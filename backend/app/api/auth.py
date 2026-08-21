from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.rate_limiter import limiter
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.models.audit_log import AuditLog
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(hours=1)

# Nom du cookie de session
AUTH_COOKIE_NAME = "sotradies_token"


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_auth_cookie(response: Response, token: str) -> None:
    """Pose le JWT en cookie httpOnly — inaccessible au JavaScript (protection XSS).

    - httponly=True  : le JS ne peut pas lire le cookie (contre le vol par XSS)
    - secure         : True en production (HTTPS uniquement)
    - samesite=lax   : le cookie n'est pas envoyé sur les requêtes cross-site
                       POST/PUT/DELETE — protection CSRF de base
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.ENV.lower() == "production",
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(email=payload.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if user.locked_until and user.locked_until > datetime.utcnow():
        minutes_restantes = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Compte temporairement bloqué suite à trop de tentatives échouées. "
                   f"Réessayez dans {minutes_restantes} minute(s).",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_ATTEMPTS:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
            db.commit()
            raise HTTPException(status_code=429, detail="Trop de tentatives échouées. Compte bloqué pendant 1 heure.")
        db.commit()
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    user.failed_login_attempts = 0
    user.locked_until = None

    token = create_access_token({"sub": user.email, "profil": user.profil})

    db.add(AuditLog(utilisateur_email=user.email, action="connexion", detail=None))
    db.commit()

    # S8 : le JWT part en cookie httpOnly, plus dans le corps de la réponse
    _set_auth_cookie(response, token)

    return {
        "user": {"email": user.email, "nom": user.nom, "profil": user.profil},
    }


@router.post("/logout")
def logout(response: Response, user: dict = Depends(get_current_user)):
    """Supprime le cookie de session côté navigateur."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"detail": "Déconnecté"}


@router.get("/me")
def get_current_user_info(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    db_user = db.query(User).filter_by(email=user["sub"]).first()

    if not db_user or not db_user.actif:
        raise HTTPException(status_code=401, detail="Session invalide")

    return {
        "user": {"email": db_user.email, "nom": db_user.nom, "profil": db_user.profil},
    }