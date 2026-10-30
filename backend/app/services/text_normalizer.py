"""
Normalisation de texte partagée (accents, casse, ponctuation) et recherche de
termes en mot entier.

Module feuille, sans dépendance métier : aucun risque d'import circulaire.
Utilisé par keyword_matcher, keyword_scorer et scoring_orchestrator.

L'arabe est translittéré par unidecode de façon déterministe : texte et
mot-clé subissent la même transformation, la correspondance reste donc valide
(« محولات » dans l'annonce et dans la configuration donnent la même forme).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable

from unidecode import unidecode

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_text(value: Any) -> str:
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    text = unidecode(str(value or "")).lower()
    return " ".join(_NON_ALNUM.sub(" ", text).split())


@lru_cache(maxsize=4096)
def _term_pattern(term: str):
    """Motif « mot entier » sur le texte normalisé (ni préfixe, ni suffixe collé)."""
    normalized = normalize_text(term)
    if not normalized:
        return None
    return re.compile(r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])")


def contains_term(text: Any, term: Any) -> bool:
    """Vrai si `term` apparaît en mot entier dans `text` (après normalisation)."""
    if not isinstance(term, str):
        return False
    pattern = _term_pattern(term)
    return bool(pattern and pattern.search(normalize_text(text)))


def first_term(text: Any, terms: Iterable[Any] | None) -> str | None:
    """Premier terme de `terms` présent en mot entier dans `text`, sinon None."""
    normalized = normalize_text(text)
    if not normalized:
        return None
    for term in terms or []:
        if not isinstance(term, str):
            continue
        pattern = _term_pattern(term)
        if pattern and pattern.search(normalized):
            return term
    return None
