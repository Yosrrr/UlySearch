from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class TenderStatusUpdate(BaseModel):
    statut: str


class TenderOut(BaseModel):
    id: str
    objet: str
    acheteur: str
    categorie: str | None
    top_categorie: str | None
    score: int
    score_details: dict[str, Any] | None = None
    raison_rejet: str | None = None

    statut: str
    commercial_assigne: str | None
    acheteur_connu: str | None

    date_publication: datetime | None
    date_limite: datetime | None
    date_detection: datetime

    source: str
    lien: str

    description_detaillee: str | None
    budget_detecte: float | None
    duree_execution: str | None
    montant_cautionnement: float | None

    type_marche: str | None
    procedure_passation: str | None
    region_execution: str | None
    date_debut_execution: date | None
    date_ouverture_offres: date | None
    lieu_ouverture_offres: str | None
    caractere_prix: str | None

    class Config:
        from_attributes = True


def _compute_rejection_reason(score_details: dict, score: int) -> str | None:
    if not score_details:
        return "Aucun mot-clé métier détecté"
    if score == 0:
        return "Aucun mot-clé métier détecté"
    return f"Score de pertinence insuffisant ({score}%)"


def _decimal_to_float(value):
    return float(value) if value is not None else None


def to_tender_out(t) -> TenderOut:
    score_details = t.score_details or {}

    best_cat, best_score = None, 0
    for cat, data in score_details.items():
        current_score = data.get("score", 0) if isinstance(data, dict) else 0
        if current_score > best_score:
            best_cat, best_score = cat, current_score

    return TenderOut(
        id=t.id,
        objet=t.objet,
        acheteur=t.acheteur,
        categorie=t.categorie,
        top_categorie=best_cat,
        score=best_score,
        score_details=t.score_details,
        raison_rejet=_compute_rejection_reason(score_details, best_score),

        statut=t.statut,
        commercial_assigne=t.commercial_assigne,
        acheteur_connu=t.acheteur_connu,

        date_publication=t.date_publication,
        date_limite=t.date_limite,
        date_detection=t.date_detection,

        source=t.source,
        lien=t.lien,

        description_detaillee=t.description_detaillee,
        budget_detecte=_decimal_to_float(t.budget_detecte),
        duree_execution=t.duree_execution,
        montant_cautionnement=_decimal_to_float(t.montant_cautionnement),

        type_marche=t.type_marche,
        procedure_passation=t.procedure_passation,
        region_execution=t.region_execution,
        date_debut_execution=t.date_debut_execution,
        date_ouverture_offres=t.date_ouverture_offres,
        lieu_ouverture_offres=t.lieu_ouverture_offres,
        caractere_prix=t.caractere_prix,
    )