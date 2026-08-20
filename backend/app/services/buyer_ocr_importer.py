"""
Import des acheteurs connus à partir d'un document scanné (PDF ou image),
via OCR (Tesseract) puis structuration par le LLM local Qwen2.5 3B (Ollama).

Contrairement à buyer_importer.py (import Excel), ce module FUSIONNE avec
la base existante au lieu de tout remplacer : chaque acheteur détecté est
d'abord comparé aux acheteurs déjà connus via le même moteur de rapprochement
flou que le pipeline (Layer 5), pour éviter les doublons créés par une
variante d'écriture différente (OCR imparfait, abréviations...).
"""
import io

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from app.core.config import settings
from sqlalchemy.orm import Session
from app.models.known_buyer import KnownBuyer
from app.services.local_llm_client import call_local_llm_json
from app.services.buyer_matcher import find_matching_buyer

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

OCR_LANG = "fra"
CHUNK_SIZE = 3000  # cohérent avec la limite déjà appliquée à Qwen ailleurs (ai_detail_extractor.py)

SYSTEM_PROMPT = """Tu lis le texte brut issu d'un OCR (reconnaissance optique de caractères) sur une liste papier scannée de clients/acheteurs publics ou privés tunisiens.
Le texte peut contenir des erreurs d'OCR, des lignes mal alignées ou du bruit — fais de ton mieux pour reconstituer les entrées malgré tout.
Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, avec exactement cette forme :
{
  "acheteurs": [
    {
      "nom_acheteur": "nom complet et propre de l'acheteur",
      "variantes": "autres écritures possibles du même nom, séparées par ; ou null",
      "client_sotradies": "Oui" ou "Non" ou null si l'information n'apparaît pas dans le texte,
      "notes": "toute information complémentaire utile trouvée sur la même ligne, ou null"
    }
  ]
}
Ignore les lignes qui ne sont manifestement pas un nom d'acheteur (en-têtes de page, numéros de page, texte parasite de l'OCR). N'invente jamais un acheteur qui n'est pas dans le texte."""


def _pdf_text_layer(pdf_bytes: bytes) -> str:
    """Tente d'abord une extraction de texte native (PDF avec vraie couche
    texte, pas juste une image) — rapide et sans erreurs OCR si disponible."""
    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _pdf_ocr(pdf_bytes: bytes) -> str:
    """PDF scanné (image) : convertit chaque page en image puis OCR."""
    kwargs = {"poppler_path": settings.POPPLER_PATH} if settings.POPPLER_PATH else {}
    images = convert_from_bytes(pdf_bytes, dpi=300, **kwargs)
    return "\n".join(pytesseract.image_to_string(img, lang=OCR_LANG) for img in images)


def _image_ocr(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang=OCR_LANG)


def extract_text(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _pdf_text_layer(file_bytes)
        if len(text) < 20:
            text = _pdf_ocr(file_bytes)
        return text
    elif lower.endswith((".jpg", ".jpeg", ".png")):
        return _image_ocr(file_bytes)
    else:
        raise ValueError("Format non supporté — utilisez un PDF, JPG ou PNG.")


def _chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def _extract_buyers_from_text(text: str) -> list[dict]:
    all_buyers = []
    for chunk in _chunks(text):
        if not chunk.strip():
            continue
        data = call_local_llm_json(SYSTEM_PROMPT, chunk)
        if data and isinstance(data.get("acheteurs"), list):
            all_buyers.extend(data["acheteurs"])
    return all_buyers


def import_buyers_from_scan(db: Session, file_bytes: bytes, filename: str) -> dict:
    """Point d'entrée principal, appelé par la route API.
    Fusionne avec la base existante (ne supprime rien), contrairement à
    l'import Excel qui remplace tout."""
    text = extract_text(file_bytes, filename)
    if not text.strip():
        return {
            "detectes": 0, "crees": 0, "fusionnes": 0, "ignores": 0,
            "avertissement": "Aucun texte exploitable détecté sur le document (OCR vide).",
        }

    raw_buyers = _extract_buyers_from_text(text)
    known_buyers = db.query(KnownBuyer).all()

    crees, fusionnes, ignores = 0, 0, 0

    for entry in raw_buyers:
        nom = (entry.get("nom_acheteur") or "").strip()
        if not nom:
            ignores += 1
            continue

        match = find_matching_buyer(nom, known_buyers)

        if match:
            existing_variantes = set(
                v.strip() for v in (match.variantes or "").split(";") if v.strip()
            )
            if nom != match.nom_acheteur:
                existing_variantes.add(nom)
            if entry.get("variantes"):
                existing_variantes.update(
                    v.strip() for v in str(entry["variantes"]).split(";") if v.strip()
                )
            match.variantes = "; ".join(sorted(existing_variantes)) or None

            if not match.notes and entry.get("notes"):
                match.notes = entry["notes"]
            if match.client_sotradies == "Non" and entry.get("client_sotradies") == "Oui":
                match.client_sotradies = "Oui"

            fusionnes += 1
        else:
            new_buyer = KnownBuyer(
                nom_acheteur=nom,
                variantes=entry.get("variantes"),
                client_sotradies=entry.get("client_sotradies") or "Non",
                notes=entry.get("notes"),
            )
            db.add(new_buyer)
            known_buyers.append(new_buyer)
            crees += 1

    db.commit()

    return {
        "detectes": len(raw_buyers),
        "crees": crees,
        "fusionnes": fusionnes,
        "ignores": ignores,
    }