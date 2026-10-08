"""
Correspondance de mots-clés français / arabe, mot par mot.

- Un mot-clé est trouvé si TOUS ses mots apparaissent à la suite dans le texte.
- Pluriel retiré sur CHAQUE mot (groupes électrogènes = groupe électrogène).
- Arabe : voyelles, hamza (أ إ آ -> ا), ال / وال / بال / لل, suffixes ات / ين / ون / ة.
- Mots entiers uniquement : « clim » ne trouve PAS « climatique ».
- Pas d'unidecode : il abîme l'arabe.
"""
import re
import unicodedata

_ARABIC_CHARS = re.compile(r"[\u0600-\u06FF]")
# voyelles + madda/hamza séparées par NFKD (0653-0655) + tatweel
_TASHKEEL = re.compile(r"[\u064B-\u0655\u0670\u0640]")
_SPLIT = re.compile(r"[^0-9a-z\u0600-\u06FF]+")

_STOPWORDS = {
    "de", "du", "des", "la", "le", "les", "l", "d", "a", "au", "aux",
    "et", "en", "pour", "un", "une", "sur", "par", "the", "of", "and",
    "و", "في", "من", "على",
}
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ات", "ين", "ون", "ه")


def _strip_latin_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        c for c in decomposed
        if not unicodedata.combining(c) or _ARABIC_CHARS.match(c)
    )


def _stem_arabic(word: str) -> str:
    word = _TASHKEEL.sub("", word)
    word = re.sub("[إأآ]", "ا", word).replace("ى", "ي").replace("ة", "ه")
    for prefix in _AR_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            word = word[len(prefix):]
            break
    for suffix in _AR_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word


def _stem_latin(word: str) -> str:
    if len(word) > 3 and word[-1] in "sx" and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    """Texte -> liste de mots normalisés (sans mots vides)."""
    if not text:
        return []
    text = _strip_latin_accents(str(text)).lower()
    text = text.replace("’", " ").replace("'", " ")
    tokens = []
    for raw in _SPLIT.split(text):
        if not raw:
            continue
        if _ARABIC_CHARS.search(raw):
            raw = _TASHKEEL.sub("", raw)
            if raw in _STOPWORDS:
                continue
            tokens.append(_stem_arabic(raw))
        else:
            if raw in _STOPWORDS:
                continue
            tokens.append(_stem_latin(raw))
    return [t for t in tokens if t]


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def match_keywords(text: str, keywords) -> list:
    """Retourne les mots-clés trouvés. Deux variantes identiques une fois
    normalisées (accent, pluriel) ne comptent qu'une seule fois."""
    if not text or not keywords:
        return []
    text_tokens = tokenize(text)
    found, seen = [], set()
    for kw in keywords:
        kw_tokens = tokenize(str(kw or ""))
        key = tuple(kw_tokens)
        if not kw_tokens or key in seen:
            continue
        if _contains_sequence(text_tokens, kw_tokens):
            seen.add(key)
            found.append(kw)
    return found