from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.core.config import settings

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
   
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
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
