from pydantic import BaseModel, ConfigDict


class BuyerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None
    nom_acheteur: str
    variantes: str | None
    client_sotradies: str
    notes: str | None



class BuyerCreate(BaseModel):
    nom_acheteur: str
    variantes: str | None = None
    client_sotradies: str = "Non"  # "Oui" | "Non"
    notes: str | None = None


class BuyerUpdate(BaseModel):
    nom_acheteur: str | None = None
    variantes: str | None = None
    client_sotradies: str | None = None
    notes: str | None = None