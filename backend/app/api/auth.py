from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.database import SessionLocal
from app.core.security import verify_password, create_access_token
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    db = SessionLocal()
    user = db.query(User).filter_by(email=payload.email).first()
    db.close()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    token = create_access_token({"sub": user.email, "profil": user.profil})
    return {
        "access_token": token,
        "user": {"email": user.email, "nom": user.nom, "profil": user.profil},
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    user = db.query(User).filter_by(email=current_user.get("sub")).first()
    db.close()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    return {
        "user": {"email": user.email, "nom": user.nom, "profil": user.profil},
    }