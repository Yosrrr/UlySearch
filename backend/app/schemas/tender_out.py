"""Schémas de sortie pour les marchés.

Deux modes :
- client  : construit depuis (CompanyTender, Sotradies)
- superadmin : construit depuis Sotradies (vue brute plateforme)
"""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TenderStatusUpdate(BaseModel):
    # Cycle de vie commercial côté client :
    # "nouveau" | "en_cours" | "sans_suite" | "gagne" | "perdu"
    # Pour superadmin (vue brute) : "nouveau" | "retenu" | "sans_suite"
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

    # decision = verdict moteur ("retenu" | "rejete") — None en vue superadmin brute
    decision: str | None = None
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

    # Identifiant interne CompanyTender (utile pour PATCH côté client)
    company_tender_id: int | None = None
    feedback: str | None = None

    model_config = ConfigDict(from_attributes=True)


def _decimal_to_float(value):
    return float(value) if value is not None else None


def _best_from_details(score_details: dict | None) -> tuple[str | None, int]:
    best_cat, best_score = None, 0
    for cat, data in (score_details or {}).items():
        if not isinstance(data, dict):
            continue
        current = int(data.get("score", 0) or 0)
        if current > best_score:
            best_cat, best_score = cat, current
    return best_cat, best_score


def _rejection_reason(score: int, decision: str | None, score_details: dict | None = None) -> str | None:
    # Seuls les marchés rejetés par le moteur d'un client ont une raison.
    # Vue superadmin (decision=None) : pas de score global, donc pas de raison.
    if decision != "rejete":
        return None
    for data in (score_details or {}).values():
        if isinstance(data, dict) and data.get("methode") == "exclusion":
            mot = data.get("mot_exclusion")
            return f"Mot d'exclusion détecté : {mot}" if mot else "Mot d'exclusion détecté"
    if score <= 0:
        return "Aucun mot-clé métier détecté"
    return f"Score de pertinence insuffisant ({score}%)"

def to_tender_out_from_sotradies(t) -> TenderOut:
    """Vue superadmin / brute : score depuis Sotradies.score_details."""
    score_details = t.score_details or {}
    best_cat, best_score = _best_from_details(score_details)

    return TenderOut(
        id=t.id,
        objet=t.objet,
        acheteur=t.acheteur,
        categorie=t.categorie,
        top_categorie=best_cat,
        score=best_score,
        score_details=score_details,
        raison_rejet=_rejection_reason(best_score, None),
        decision=None,
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
        company_tender_id=None,
    )


def to_tender_out_from_match(match, tender, commercial_nom: str | None = None) -> TenderOut:
    """Vue client : score/statut/commercial depuis CompanyTender."""
    score_details = match.score_details or {}
    best_cat, best_score = _best_from_details(score_details)

    # Preferer le score stocke sur CompanyTender
    score = int(
        match.score
        if match.score is not None
        else best_score
    )
    top_cat = match.categorie or best_cat

    return TenderOut(
        id=tender.id,
        objet=tender.objet,
        acheteur=tender.acheteur,
        categorie=top_cat,
        top_categorie=top_cat,
        score=score,
        score_details=score_details,
        raison_rejet=_rejection_reason(score, match.decision, score_details),
        decision=match.decision,
        statut=match.statut,
        commercial_assigne=commercial_nom,
        acheteur_connu=match.acheteur_connu or tender.acheteur_connu,
        date_publication=tender.date_publication,
        date_limite=tender.date_limite,
        date_detection=tender.date_detection,
        source=tender.source,
        lien=tender.lien,
        description_detaillee=tender.description_detaillee,
        budget_detecte=_decimal_to_float(tender.budget_detecte),
        duree_execution=tender.duree_execution,
        montant_cautionnement=_decimal_to_float(tender.montant_cautionnement),
        type_marche=tender.type_marche,
        procedure_passation=tender.procedure_passation,
        region_execution=tender.region_execution,
        date_debut_execution=tender.date_debut_execution,
        date_ouverture_offres=tender.date_ouverture_offres,
        lieu_ouverture_offres=tender.lieu_ouverture_offres,
        caractere_prix=tender.caractere_prix,
        company_tender_id=match.id,
        feedback=match.feedback,
    )


# Alias de compatibilite pour l'ancien code
def to_tender_out(t) -> TenderOut:
    return to_tender_out_from_sotradies(t)


class TenderListPage(BaseModel):
    
    items: list[TenderOut]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total