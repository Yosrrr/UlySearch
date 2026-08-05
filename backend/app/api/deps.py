from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

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
