from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.database import get_db
from app.models.user import User

AUTH_COOKIE_NAME = "sotradies_token"


def _extract_token(request: Request) -> str | None:
    """Extrait le JWT : cookie httpOnly en priorité (S8),
    header Authorization Bearer en secours (tests API, outils)."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    email = payload.get("sub")
    user = db.query(User).filter_by(email=email).first()
    if not user or not user.actif:
        raise HTTPException(status_code=401, detail="Session invalide")

    payload["profil"] = user.profil
    payload["nom"] = user.nom
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("profil") != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user


def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("profil") != "superadmin":
        raise HTTPException(status_code=403, detail="Accès réservé au super-administrateur")
    return user


def require_admin_or_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("profil") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user