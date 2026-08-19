from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import SessionLocal
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(hours=1)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    db = SessionLocal()
    user = db.query(User).filter_by(email=payload.email).first()

    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    # Compte actuellement bloqué : refuser sans même vérifier le mot de passe
    if user.locked_until and user.locked_until > datetime.utcnow():
        minutes_restantes = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        db.close()
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
            db.close()
            raise HTTPException(
                status_code=429,
                detail=f"Trop de tentatives échouées. Compte bloqué pendant 1 heure.",
            )
        db.commit()
        tentatives_restantes = MAX_ATTEMPTS - user.failed_login_attempts
        db.close()
        raise HTTPException(
            status_code=401,
            detail=f"Email ou mot de passe incorrect ({tentatives_restantes} tentative(s) restante(s) avant blocage).",
        )

    if not user.actif:
        db.close()
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    # Connexion réussie : on réinitialise le compteur
    user.failed_login_attempts = 0
    user.locked_until = None

    token = create_access_token({"sub": user.email, "profil": user.profil})

    db.add(AuditLog(utilisateur_email=user.email, action="connexion", detail=None))
    db.commit()
    db.close()

    return {
        "access_token": token,
        "user": {"email": user.email, "nom": user.nom, "profil": user.profil},
    }
    
@router.get("/me")
def get_current_user_info(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    db_user = db.query(User).filter_by(email=user["sub"]).first()
    db.close()

    if not db_user or not db_user.actif:
        raise HTTPException(status_code=401, detail="Session invalide")

    return {
        "user": {"email": db_user.email, "nom": db_user.nom, "profil": db_user.profil},
    }