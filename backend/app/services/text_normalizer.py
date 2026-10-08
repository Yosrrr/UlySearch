import re
import unicodedata
from unidecode import unidecode

def normalize_latin(text: str) -> str:
    """Nettoie le texte en français/anglais (enlève accents, majuscules)."""
    text = unidecode(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())

def normalize_arabic(text: str) -> str:
    """Nettoie le texte en arabe (enlève les articles Al-, les pluriels)."""
    if not text: return ""
    # Enlève les accents arabes (tashkeel)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Unifie les lettres (Alif, Ta marbuta, etc.)
    text = re.sub("[إأآا]", "ا", text)
    text = re.sub("ة", "ه", text)
    text = re.sub("ى", "ي", text)
    # Enlève l'article "AL" au début des mots
    text = re.sub(r"\bال", "", text)
    return text.strip()

def split_scripts(text: str) -> dict:
    """Sépare le français de l'arabe pour les traiter séparément."""
    latin_parts = []
    arabic_parts = []
    for word in (text or "").split():
        if any("\u0600" <= c <= "\u06FF" for c in word):
            arabic_parts.append(normalize_arabic(word))
        else:
            latin_parts.append(normalize_latin(word))
    return {
        "latin": " ".join(latin_parts),
        "arabic": " ".join(arabic_parts)
    }