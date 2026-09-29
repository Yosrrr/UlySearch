from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SotradiesRaw(BaseModel):
    """
    Données brutes d'un marché récupéré par un scraper.

    Les champs enrichis (description_detaillee, type_marche, etc.)
    sont remplis par le scraper universel depuis la page de détail.
    Pour ONMP et TUNEPS, ils sont remplis par ai_filter_and_extract
    (Phase 3 du pipeline).
    """

    source: str
    reference: Optional[str] = None
    objet: str = Field(..., min_length=3)
    acheteur: str = Field(default="Non précisé", min_length=1)
    categorie: Optional[str] = None
    date_publication: Optional[datetime] = None
    date_limite: Optional[datetime] = None
    budget_estime: Optional[float] = None
    lien: Optional[str] = None

    # ── Champs enrichis par le scraper universel (page de détail) ──
    # Pour ONMP/TUNEPS, ces champs sont remplis plus tard par l'IA (Phase 3).
    description_detaillee: Optional[str] = None
    type_marche: Optional[str] = None
    procedure_passation: Optional[str] = None
    region_execution: Optional[str] = None
    lieu_ouverture_offres: Optional[str] = None
    caractere_prix: Optional[str] = None