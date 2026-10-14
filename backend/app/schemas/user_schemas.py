
import re
from pydantic import BaseModel, EmailStr, field_validator , ConfigDict

_PASSWORD_MIN = 8

def _validate_password(value: str) -> str:
    if len(value) < _PASSWORD_MIN:
        raise ValueError(f"Mot de passe trop court ({_PASSWORD_MIN} caractères minimum).")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Mot de passe trop long (72 octets maximum).")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Le mot de passe doit contenir des lettres et des chiffres.")
    return value

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
    company_id: int | None = None

    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        return _validate_password(v)


class UserUpdate(BaseModel):
    nom: str | None = None
    profil: str | None = None
    password: str | None = None  # si fourni, réinitialise le mot de passe
    actif: bool | None = None
    
    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        return _validate_password(v) if v else v