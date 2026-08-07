import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.core.database import SessionLocal
from app.models.known_buyer import KnownBuyer
from app.schemas.buyer import BuyerOut, BuyerCreate, BuyerUpdate
from app.services.buyer_importer import import_known_buyers
from app.api.deps import get_current_user

router = APIRouter(prefix="/buyers", tags=["buyers"])


@router.get("", response_model=list[BuyerOut])
def list_buyers(user=Depends(get_current_user)):
    db = SessionLocal()
    buyers = db.query(KnownBuyer).order_by(KnownBuyer.nom_acheteur).all()
    db.close()
    return buyers


@router.post("", response_model=BuyerOut)
def create_buyer(payload: BuyerCreate, user=Depends(get_current_user)):
    nom = payload.nom_acheteur.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom de l'acheteur est obligatoire.")

    db = SessionLocal()
    existing = db.query(KnownBuyer).filter(KnownBuyer.nom_acheteur == nom).first()
    if existing:
        db.close()
        raise HTTPException(status_code=409, detail="Un acheteur avec ce nom existe déjà.")

    buyer = KnownBuyer(
        nom_acheteur=nom,
        variantes=payload.variantes,
        client_sotradies=payload.client_sotradies or "Non",
        notes=payload.notes,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    db.close()
    return buyer


@router.post("/import")
async def import_buyers(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Le fichier doit être un Excel (.xlsx ou .xls).")

    contents = await file.read()
    try:
        count = import_known_buyers(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de l'import : {exc}")

    return {"imported": count}


@router.patch("/{buyer_id}", response_model=BuyerOut)
def update_buyer(buyer_id: int, payload: BuyerUpdate, user=Depends(get_current_user)):
    db = SessionLocal()
    buyer = db.query(KnownBuyer).filter_by(id=buyer_id).first()
    if not buyer:
        db.close()
        raise HTTPException(status_code=404, detail="Acheteur introuvable.")

    if payload.nom_acheteur is not None:
        buyer.nom_acheteur = payload.nom_acheteur
    if payload.variantes is not None:
        buyer.variantes = payload.variantes
    if payload.client_sotradies is not None:
        buyer.client_sotradies = payload.client_sotradies
    if payload.notes is not None:
        buyer.notes = payload.notes

    db.commit()
    db.refresh(buyer)
    db.close()
    return buyer