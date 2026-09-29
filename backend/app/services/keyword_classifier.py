"""Moteur robuste de classification et d'exclusion par mots-clés (mot entier, pluriels, sans accents)."""
import re
from functools import lru_cache

from rapidfuzz import fuzz
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
    # Ajoute une tolérance pour les pluriels (-s, -x, -es)
    parts = [re.escape(token) + r"(?:s|x|es)?" for token in tokens]
    # (?<![a-z0-9]) et (?![a-z0-9]) garantissent qu'on matche le mot entier
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


def score_for_category(tender, category: str, dynamic_categories: dict, dynamic_exclusions: list[str]) -> tuple[int, list[str]]:
    text = (getattr(tender, "objet", "") or "") + " " + (getattr(tender, "categorie", "") or "")
    
    if first_matching_keyword(text, dynamic_exclusions):
        return 0, []

    category_data = dynamic_categories.get(category, {})
    keywords = category_data.get("keywords", [])
    matches = [kw for kw in keywords if contains_keyword(text, kw)]

    if not matches:
        return 0, []

    score = min(100, 60 + 15 * (len(matches) - 1))
    return score, matches


def score_all_categories(tender, dynamic_categories: dict, dynamic_exclusions: list[str]) -> dict:
    result = {}
    for category in dynamic_categories:
        score, matches = score_for_category(tender, category, dynamic_categories, dynamic_exclusions)
        result[category] = {"score": score, "mots_cles_matches": matches}
    return result


def _best_fuzzy_score(text: str, dynamic_categories: dict) -> int:
    normalized_text = normalize_text(text)
    best = 0
    for cat_data in dynamic_categories.values():
        for kw in cat_data.get("keywords", []):
            score = fuzz.partial_ratio(normalize_text(kw), normalized_text)
            if score > best:
                best = score
    return best


def needs_ai_fallback(tender, score_details: dict, dynamic_categories: dict, dynamic_exclusions: list[str]) -> bool:
    if any(d.get("score", 0) > 0 for d in score_details.values()):
        return False
    text = getattr(tender, "objet", "") or ""
    if first_matching_keyword(text, dynamic_exclusions):
        return False
    return _best_fuzzy_score(text, dynamic_categories) >= 70