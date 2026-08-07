from pydantic import BaseModel


class BuyerOut(BaseModel):
    id: int
    nom_acheteur: str
    variantes: str | None
    client_sotradies: str
    notes: str | None

    class Config:
        from_attributes = True


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