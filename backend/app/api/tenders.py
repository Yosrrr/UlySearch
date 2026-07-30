# app/api/tenders.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from app.core.database import get_db
from app.models.sotradies import Sotradies  # ⚠️ adaptez le chemin si le fichier est ailleurs
from app.schemas.tender import TenderOut, extract_best_score

router = APIRouter(prefix="/tenders", tags=["tenders"])


def _to_out(t: Sotradies) -> TenderOut:
    score, top_categorie = extract_best_score(t.score_details)
    return TenderOut(
        id=t.id, reference=t.reference, objet=t.objet, acheteur=t.acheteur,
        categorie=t.categorie, date_publication=t.date_publication,
        date_limite=t.date_limite, budget_estime=t.budget_estime, source=t.source,
        lien=t.lien, date_detection=t.date_detection, statut=t.statut,
        commercial_assigne=t.commercial_assigne, score_details=t.score_details,
        score=score, top_categorie=top_categorie,
    )


@router.get("", response_model=list[TenderOut])
def list_tenders(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    categorie: Optional[str] = None,
    statut: Optional[str] = None,
    commercial: Optional[str] = None,
    score_min: Optional[int] = None,
):
    query = db.query(Sotradies)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Sotradies.objet.ilike(like), Sotradies.acheteur.ilike(like)))
    if categorie and categorie != "Toutes":
        query = query.filter(Sotradies.categorie == categorie)
    if statut and statut != "Tous":
        query = query.filter(Sotradies.statut == statut)
    if commercial and commercial != "Tous":
        query = query.filter(Sotradies.commercial_assigne == commercial)

    tenders = query.order_by(Sotradies.date_detection.desc()).limit(300).all()
    results = [_to_out(t) for t in tenders]

    if score_min:
        results = [r for r in results if r.score >= score_min]

    return results


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Sotradies).filter(Sotradies.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Marché introuvable.")
    return _to_out(tender)