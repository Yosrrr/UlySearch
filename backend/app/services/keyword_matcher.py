"""
Correspondance de mots-clés : mot entier, accents, pluriels simples.

Usage :
- exclusions du client (rejet dur, sans IA) ;
- indices tracés dans mots_cles_matches (ils ne décident pas seuls).

Les fautes de frappe ne sont pas gérées ici : c'est le rôle de l'IA contextuelle.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.services.text_normalizer import normalize_text

__all__ = [
    "normalize_text",
    "contains_keyword",
    "first_matching_keyword",
    "match_keywords",
]


@lru_cache(maxsize=4096)
def _pattern(keyword: str) -> re.Pattern | None:
    tokens = normalize_text(keyword).split()
    if not tokens:
        return None
    parts = [re.escape(token) + r"(?:s|x|es)?" for token in tokens]
    return re.compile(r"(?<![a-z0-9])" + r"\s+".join(parts) + r"(?![a-z0-9])")


def contains_keyword(text: Any, keyword: Any) -> bool:
    if not isinstance(keyword, str):
        return False
    pattern = _pattern(keyword)
    return bool(pattern and pattern.search(normalize_text(text)))


def first_matching_keyword(text: Any, keywords: Any) -> str | None:
    normalized = normalize_text(text)
    for keyword in keywords or []:
        if not isinstance(keyword, str):
            continue
        pattern = _pattern(keyword)
        if pattern and pattern.search(normalized):
            return keyword
    return None


def match_keywords(text: Any, keywords: Any) -> list[str]:
    normalized = normalize_text(text)
    found: list[str] = []
    for keyword in keywords or []:
        if not isinstance(keyword, str) or keyword in found:
            continue
        pattern = _pattern(keyword)
        if pattern and pattern.search(normalized):
            found.append(keyword)
    return found
