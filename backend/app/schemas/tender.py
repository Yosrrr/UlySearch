# app/schemas/tender.py
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Literal


class TenderOut(BaseModel):
    id: str
    reference: Optional[str] = None
    objet: str
    acheteur: str
    categorie: Optional[str] = None
    date_publication: Optional[datetime] = None
    date_limite: Optional[datetime] = None
    budget_estime: Optional[Decimal] = None
    source: str
    lien: str
    date_detection: datetime
    statut: Literal["nouveau", "retenu", "sans_suite"]
    commercial_assigne: Optional[str] = None
    score_details: Optional[Any] = None
    score: int = 0
    top_categorie: Optional[str] = None  # ex. "MATERIEL_ROULANT" — la catégorie qui a produit le meilleur score

    class Config:
        from_attributes = True


def extract_best_score(score_details) -> tuple[int, Optional[str]]:
    """score_details a la forme :
    {"MATERIEL_ROULANT": {"score": 90, "mots_cles_matches": [...]}, "ENGINS_TP": {"score": 0, ...}, ...}
    """
    if not score_details or not isinstance(score_details, dict):
        return 0, None

    numeric_items = {}
    for category, value in score_details.items():
        if isinstance(value, dict) and isinstance(value.get("score"), (int, float)):
            numeric_items[category] = value["score"]
        elif isinstance(value, (int, float)):  # tolère aussi une forme à plat si elle existe ailleurs
            numeric_items[category] = value

    if not numeric_items:
        return 0, None

    best_key = max(numeric_items, key=numeric_items.get)
    return int(numeric_items[best_key]), best_key