from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.core.security import verify_password, create_access_token
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

    token = create_access_token({"sub": user.email, "profil": user.profil})
    return {
        "access_token": token,
        "user": {"email": user.email, "nom": user.nom, "profil": user.profil},
    }