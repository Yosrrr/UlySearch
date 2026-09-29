"""Correspondance de mots-clés sans faux positifs (mot entier, accents, pluriels)."""
import re
from functools import lru_cache

from unidecode import unidecode


def normalize_text(value) -> str:
    text = unidecode(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=4096)
def _keyword_pattern(keyword: str):
    tokens = normalize_text(keyword).split()
    if not tokens:
        return None
    parts = [re.escape(token) + r"(?:s|x|es)?" for token in tokens]
    return re.compile(r"(?<![a-z0-9])" + r"\s+".join(parts) + r"(?![a-z0-9])")


def contains_keyword(text, keyword) -> bool:
    if not isinstance(keyword, str):
        return False
    pattern = _keyword_pattern(keyword)
    return bool(pattern and pattern.search(normalize_text(text)))


def first_matching_keyword(text, keywords) -> str | None:
    normalized = normalize_text(text)
    for keyword in keywords or []:
        if not isinstance(keyword, str):
            continue
        pattern = _keyword_pattern(keyword)
        if pattern and pattern.search(normalized):
            return keyword
    return None