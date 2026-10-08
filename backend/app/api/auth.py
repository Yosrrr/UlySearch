from sqlalchemy import func
import time
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



# F-014 : compteur d'échecs par (email, IP) — un tiers ne peut plus bloquer le compte.
FAIL_WINDOW_SECONDS = 15 * 60
_mem_fails: dict[str, tuple[int, float]] = {}


def _redis():
    try:
        import redis as _r
        return _r.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
    except Exception:
        return None


def _fail_key(email: str, ip: str) -> str:
    return f"loginfail:{email}:{ip}"


def _fail_count(email: str, ip: str) -> int:
    key = _fail_key(email, ip)
    try:
        return int(_redis().get(key) or 0)
    except Exception:
        n, exp = _mem_fails.get(key, (0, 0.0))
        return n if exp > time.time() else 0


def _register_failure(email: str, ip: str) -> int:
    key = _fail_key(email, ip)
    try:
        r = _redis()
        n = r.incr(key)
        r.expire(key, FAIL_WINDOW_SECONDS)
        return int(n)
    except Exception:
        n = _fail_count(email, ip) + 1
        _mem_fails[key] = (n, time.time() + FAIL_WINDOW_SECONDS)
        return n


def _reset_failures(email: str, ip: str) -> None:
    key = _fail_key(email, ip)
    try:
        _redis().delete(key)
    except Exception:
        pass
    _mem_fails.pop(key, None)

@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    ip = request.client.host if request.client else "inconnu"

    if _fail_count(email, ip) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429,
                            detail="Trop de tentatives depuis cet appareil. Réessayez dans 15 minutes.")

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        if _register_failure(email, ip) >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429,
                                detail="Trop de tentatives depuis cet appareil. Réessayez dans 15 minutes.")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    _reset_failures(email, ip)
    user.failed_login_attempts = 0
    user.locked_until = None

    token = create_access_token({"sub": user.email, "profil": user.profil,
                                 "tv": getattr(user, "token_version", 0) or 0})
    db.add(AuditLog(utilisateur_email=user.email, action="connexion", detail=None))
    db.commit()
    _set_auth_cookie(response, token)
    return {"user": {"email": user.email, "nom": user.nom, "profil": user.profil}}


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """F-015 : invalide TOUS les jetons de cet utilisateur, puis supprime le cookie."""
    db_user = db.query(User).filter_by(email=user["sub"]).first()
    if db_user:
        db_user.token_version = (db_user.token_version or 0) + 1
        db.add(AuditLog(utilisateur_email=db_user.email, action="deconnexion", detail=None))
        db.commit()
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