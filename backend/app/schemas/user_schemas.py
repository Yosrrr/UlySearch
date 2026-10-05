from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nom: str
    profil: str
    actif: bool



class UserCreate(BaseModel):
    email: EmailStr
    nom: str
    password: str
    profil: str = "user"
    company_id: int | None = None # "admin" | "user" | "superadmin"


class UserUpdate(BaseModel):
    nom: str | None = None
    profil: str | None = None
    password: str | None = None  # si fourni, réinitialise le mot de passe
    actif: bool | None = None