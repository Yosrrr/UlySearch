from datetime import datetime
from typing import Any
from pydantic import BaseModel


class TenderOut(BaseModel):
    id: str
    objet: str
    acheteur: str
    categorie: str | None
    top_categorie: str | None
    score: int
    score_details: dict[str, Any] | None = None
    statut: str
    commercial_assigne: str | None
    acheteur_connu: str | None
    date_publication: datetime | None
    date_limite: datetime | None
    date_detection: datetime
    source: str
    lien: str

    class Config:
        from_attributes = True


def to_tender_out(t) -> TenderOut:
    """Convertit un enregistrement Sotradies (score par catégorie) en
    TenderOut (score unique + catégorie dominante), format attendu
    par le frontend."""
    score_details = t.score_details or {}
    best_cat, best_score = None, 0
    for cat, data in score_details.items():
        if data.get("score", 0) > best_score:
            best_cat, best_score = cat, data["score"]

    return TenderOut(
        id=t.id,
        objet=t.objet,
        acheteur=t.acheteur,
        categorie=t.categorie,
        top_categorie=best_cat,
        score=best_score,
        score_details=t.score_details,
        statut=t.statut,
        commercial_assigne=t.commercial_assigne,
        acheteur_connu=t.acheteur_connu,
        date_publication=t.date_publication,
        date_limite=t.date_limite,
        date_detection=t.date_detection,
        source=t.source,
        lien=t.lien,
    )