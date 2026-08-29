"""CRUD des commerciaux (nom + email) — réservé aux admins.

Résout le constat §2 de la revue n°2 : la table commercials existe
mais aucun endpoint ne permet de la peupler autrement qu'en SQL direct.
"""
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.models.commercial import Commercial
from app.api.deps import require_admin_or_superadmin

router = APIRouter(prefix="/admin/commercials", tags=["admin-commercials"])


class CommercialCreate(BaseModel):
    nom: str
    email: EmailStr
    actif: bool = True


class CommercialUpdate(BaseModel):
    nom: str | None = None
    email: EmailStr | None = None
    actif: bool | None = None


class CommercialOut(BaseModel):
    id: int
    nom: str
    email: str
    actif: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[CommercialOut])
def list_commercials(
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    return db.query(Commercial).order_by(Commercial.nom).all()


@router.post("", response_model=CommercialOut, status_code=201)
def create_commercial(
    payload: CommercialCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    nom = payload.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom est obligatoire.")

    if db.query(Commercial).filter(Commercial.nom == nom).first():
        raise HTTPException(status_code=409, detail="Un commercial avec ce nom existe déjà.")

    if db.query(Commercial).filter(Commercial.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Un commercial avec cet email existe déjà.")

    row = Commercial(nom=nom, email=payload.email, actif=payload.actif)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{commercial_id}", response_model=CommercialOut)
def update_commercial(
    commercial_id: int,
    payload: CommercialUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    row = db.query(Commercial).filter_by(id=commercial_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Commercial introuvable.")

    if payload.nom is not None:
        row.nom = payload.nom.strip()
    if payload.email is not None:
        row.email = payload.email
    if payload.actif is not None:
        row.actif = payload.actif

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{commercial_id}", status_code=204)
def delete_commercial(
    commercial_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    row = db.query(Commercial).filter_by(id=commercial_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Commercial introuvable.")

    db.delete(row)
    db.commit()