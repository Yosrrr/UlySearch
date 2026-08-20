import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.known_buyer import KnownBuyer
from app.schemas.buyer import BuyerOut, BuyerCreate, BuyerUpdate
from app.services.buyer_importer import import_known_buyers
from app.services.buyer_ocr_importer import import_buyers_from_scan
from app.api.deps import get_current_user

router = APIRouter(prefix="/buyers", tags=["buyers"])

MAX_SCAN_SIZE = 15 * 1024 * 1024  # 15 Mo
MAGIC_BYTES = {b"%PDF": "pdf", b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


def _detect_real_type(contents: bytes) -> str | None:
    for magic, filetype in MAGIC_BYTES.items():
        if contents.startswith(magic):
            return filetype
    return None


@router.get("", response_model=list[BuyerOut])
def list_buyers(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(KnownBuyer).order_by(KnownBuyer.nom_acheteur).all()


@router.post("", response_model=BuyerOut)
def create_buyer(payload: BuyerCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    nom = payload.nom_acheteur.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom de l'acheteur est obligatoire.")

    existing = db.query(KnownBuyer).filter(KnownBuyer.nom_acheteur == nom).first()
    if existing:
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
    return buyer


@router.post("/import")
async def import_buyers(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Le fichier doit être un Excel (.xlsx ou .xls).")

    contents = await file.read()
    try:
        count = import_known_buyers(db, io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de l'import : {exc}")

    return {"imported": count}


@router.post("/import-scan")
async def import_buyers_scan(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    allowed = (".pdf", ".jpg", ".jpeg", ".png")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF, JPG ou PNG.")

    contents = await file.read()

    if len(contents) > MAX_SCAN_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (15 Mo max).")

    real_type = _detect_real_type(contents)
    if real_type is None:
        raise HTTPException(status_code=400, detail="Le contenu du fichier ne correspond à aucun format supporté (PDF/JPG/PNG).")
    if real_type == "pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="L'extension ne correspond pas au contenu réel du fichier.")
    if real_type == "png" and not file.filename.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="L'extension ne correspond pas au contenu réel du fichier.")

    try:
        result = import_buyers_from_scan(db, contents, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de l'analyse du document : {exc}")

    return result


@router.patch("/{buyer_id}", response_model=BuyerOut)
def update_buyer(buyer_id: int, payload: BuyerUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    buyer = db.query(KnownBuyer).filter_by(id=buyer_id).first()
    if not buyer:
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
    return buyer