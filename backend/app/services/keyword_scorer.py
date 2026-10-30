"""Correspondance de mots-clés (mot entier, accents, pluriels, fautes de frappe)."""
import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz.distance import OSA

# Ré-exporté : d'autres modules font `from ...keyword_scorer import normalize_text`
from app.services.text_normalizer import normalize_text

__all__ = [
    "normalize_text",
    "contains_keyword",
    "first_matching_keyword",
    "match_keyword",
    "KeywordMatch",
]


@dataclass(frozen=True)
class KeywordMatch:
    keyword: str
    kind: str  # "exact" | "fuzzy"


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


# --- Fuzzy (fautes de frappe), opt-in : contains_keyword reste exact ---------

def _max_edits(token: str) -> int:
    n = len(token)
    if n <= 4:
        return 0  # mots courts : exact uniquement
    return 1 if n <= 8 else 2


def _token_close(kw_tok: str, tok: str) -> bool:
    if tok == kw_tok:
        return True
    k = _max_edits(kw_tok)
    return (
        k > 0
        and not kw_tok.isdigit()
        and tok[:1] == kw_tok[:1]                       # filtre bon marché
        and abs(len(tok) - len(kw_tok)) <= k
        and OSA.distance(kw_tok, tok, score_cutoff=k) <= k
    )


def match_keyword(text, keyword, allow_fuzzy: bool = True) -> KeywordMatch | None:
    """Exact d'abord ; sinon tolérance de fautes sur une fenêtre contiguë de tokens."""
    if not isinstance(keyword, str):
        return None
    pattern = _keyword_pattern(keyword)
    if pattern is None:
        return None
    normalized = normalize_text(text)
    if pattern.search(normalized):
        return KeywordMatch(keyword, "exact")
    if not allow_fuzzy:
        return None
    kw_tokens = normalize_text(keyword).split()
    tokens = normalized.split()
    m = len(kw_tokens)
    for i in range(len(tokens) - m + 1):
        if all(_token_close(k, t) for k, t in zip(kw_tokens, tokens[i:i + m])):
            return KeywordMatch(keyword, "fuzzy")
    return None
