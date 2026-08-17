from datetime import datetime
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    sotradies_id: str | None
    tender_objet: str | None = None  # rempli via jointure, pour affichage lisible
    utilisateur_email: str
    action: str
    detail: str | None
    date_action: datetime

    class Config:
        from_attributes = True