from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: str
    nom: str
    profil: str
    actif: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    nom: str
    password: str
    profil: str = "user"  # "admin" | "user" | "superadmin"


class UserUpdate(BaseModel):
    nom: str | None = None
    profil: str | None = None
    password: str | None = None  # si fourni, réinitialise le mot de passe
    actif: bool | None = None