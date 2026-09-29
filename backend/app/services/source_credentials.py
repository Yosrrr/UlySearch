"""Chiffrement réversible des identifiants de sites privés."""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SOURCE_CREDENTIALS_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_source_password(password: str) -> str:
    return _fernet().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_source_password(value: str) -> str:
    return _fernet().decrypt(value.encode("ascii")).decode("utf-8")