import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from app.services.buyer_rematcher import rematch_company_tenders 
from app.core.database import get_db
from app.models.known_buyer import KnownBuyer
from app.schemas.buyer import BuyerOut, BuyerCreate, BuyerUpdate
from app.services.buyer_importer import import_known_buyers
from app.services.buyer_ocr_importer import import_buyers_from_scan
from app.api.deps import get_current_user, require_admin_or_superadmin

router = APIRouter(prefix="/buyers", tags=["buyers"])
MAX_SCAN_SIZE = 15 * 1024 * 1024  
MAGIC_BYTES = {b"%PDF": "pdf", b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


def _detect_real_type(contents: bytes) -> str | None:
    for magic, filetype in MAGIC_BYTES.items():
        if contents.startswith(magic):
            return filetype
    return None


def _buyer_query(db: Session, user):
    query = db.query(KnownBuyer)
    if user.get("profil") == "superadmin":
        return query
    company_id = user.get("company_id")
    if company_id is None:
        raise HTTPException(status_code=403, detail="Compte non rattaché à une entreprise.")
    return query.filter(KnownBuyer.company_id == int(company_id))


@router.get("", response_model=list[BuyerOut])
def list_buyers(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _buyer_query(db, user).order_by(KnownBuyer.nom_acheteur).all()


    
@router.post("", response_model=BuyerOut)
def create_buyer(
    payload: BuyerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    nom = payload.nom_acheteur.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom de l'acheteur est obligatoire.")

    query = _buyer_query(db, user)
    existing = query.filter(KnownBuyer.nom_acheteur == nom).first()
    if existing:
        raise HTTPException(status_code=409, detail="Un acheteur avec ce nom existe déjà.")

    buyer = KnownBuyer(
        company_id=None if user.get("profil") == "superadmin" else int(user["company_id"]),
        nom_acheteur=nom,
        variantes=payload.variantes,
        client_sotradies=payload.client_sotradies or "Non",
        notes=payload.notes,
    )
    db.add(buyer)
    db.commit()
    background_tasks.add_task(rematch_company_tenders, buyer.company_id)
    db.refresh(buyer)
    
    return buyer


MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10 Mo

@router.post("/import")
def import_buyers(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    contents = file.file.read()

    if len(contents) > MAX_IMPORT_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (10 Mo maximum).")

    filename = (file.filename or "").lower()
    if not any(filename.endswith(ext) for ext in (".xlsx", ".xls", ".csv")):
        raise HTTPException(422, "Format non supporté : xlsx, xls ou csv attendu.")

    company_id = user.get("company_id")
    try:
        count = import_known_buyers(db, io.BytesIO(contents), company_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(422, "Fichier illisible ou format inattendu.")

    if background_tasks is not None:
        background_tasks.add_task(rematch_company_tenders, company_id)

    return {"importes": count}


@router.post("/import-scan")
def import_buyers_scan(    
    background_tasks: BackgroundTasks,                    # def → threadpool, event loop libre (AVAIL-001)
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    contents = file.file.read()          # ← et non 'await file.read()'

    if len(contents) > MAX_SCAN_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (15 Mo maximum).")

    real_type = _detect_real_type(contents)
    if real_type is None:
        raise HTTPException(422, "Format non reconnu (PDF, JPG ou PNG attendu).")

    company_id = user.get("company_id")
    try:
        result = import_buyers_from_scan(db, contents, file.filename, company_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    background_tasks.add_task(rematch_company_tenders, company_id)
    return result


@router.patch("/{buyer_id}", response_model=BuyerOut)
def update_buyer(
    buyer_id: int,
    payload: BuyerUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    buyer = _buyer_query(db, user).filter(KnownBuyer.id == buyer_id).first()
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
    background_tasks.add_task(rematch_company_tenders, buyer.company_id)
    db.refresh(buyer)
    
    return buyer
