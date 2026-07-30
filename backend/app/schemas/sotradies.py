from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SotradiesRaw(BaseModel):
    reference: Optional[str] = None
    objet: str = Field(..., min_length=3)
    acheteur: str = Field(..., min_length=2)
    categorie: Optional[str] = None
    date_publication: Optional[datetime] = None
    date_limite: Optional[datetime] = None
    budget_estime: Optional[float] = None
    source: str
    lien: str