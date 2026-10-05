"""
Gestion des comptes utilisateurs (création, modification, suppression,
activation/désactivation). Réservé exclusivement au profil "superadmin".
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user_schemas import UserOut, UserCreate, UserUpdate
from app.api.deps import require_superadmin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

VALID_PROFILES = ("user", "admin", "commercial", "superadmin")



@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin=Depends(require_superadmin)):
    return db.query(User).order_by(User.nom).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin=Depends(require_superadmin)):
    if payload.profil not in VALID_PROFILES:
        raise HTTPException(status_code=400, detail="Profil invalide")

    # Un commercial ou admin client DOIT avoir une entreprise
    if payload.profil in ("commercial", "admin", "user") and payload.company_id is None:
        raise HTTPException(
            status_code=422,
            detail="company_id est obligatoire pour ce profil.",
        )

    # Vérifier que l'entreprise existe
    if company is None:
            raise HTTPException(status_code=404, detail="Entreprise introuvable.")

    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=409, detail="Email déjà utilisé.")

    user = User(
        email=payload.email,
        nom=payload.nom,
        password_hash=hash_password(payload.password),
        profil=payload.profil,
        company_id=payload.company_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin=Depends(require_superadmin)):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.email == admin["sub"] and payload.profil and payload.profil != user.profil:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier vos propres droits")

    if user.email == admin["sub"] and payload.actif is False:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")

    if payload.nom is not None:
        user.nom = payload.nom
    if payload.profil is not None:
        if payload.profil not in VALID_PROFILES:
            raise HTTPException(status_code=400, detail="Profil invalide")
        user.profil = payload.profil
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.actif is not None:
        user.actif = payload.actif

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_superadmin)):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.email == admin["sub"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")

    db.delete(user)
    db.commit()