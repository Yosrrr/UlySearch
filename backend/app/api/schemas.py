from pydantic import BaseModel


class SotradieOut(BaseModel):
    id: str
    reference: str
    objet: str
    acheteur: str
    source: str
    marque: str
    categorie: str
    type_marche: str
    score: int
    is_client_existant: bool
    statut: str
    date_publication: str
    date_limite: str
    budget: str
    commercial: str
