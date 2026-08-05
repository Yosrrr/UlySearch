"""
Scoring de pertinence par mots-clés (Layer 4, Tier 1) — par catégorie,
avec assignation commerciale directement issue de la même table.
"""
from unidecode import unidecode

from app.core.keywords import CATEGORIES, EXCLUSION_KEYWORDS
from app.schemas.sotradies import SotradiesRaw


def _normalize(text: str) -> str:
    return unidecode(text or "").lower()


def score_for_category(tender: SotradiesRaw, category: str) -> tuple[int, list[str]]:
    text = _normalize(tender.objet) + " " + _normalize(tender.categorie or "")

    if any(_normalize(kw) in text for kw in EXCLUSION_KEYWORDS):
        return 0, []

    keywords = CATEGORIES[category]["keywords"]
    matches = [kw for kw in keywords if _normalize(kw) in text]

    if not matches:
        return 0, []

    score = min(100, 60 + 15 * (len(matches) - 1))
    return score, matches


def score_all_categories(tender: SotradiesRaw) -> dict:
    """Retourne le détail complet du scoring, prêt à stocker dans score_details."""
    result = {}
    for category in CATEGORIES:
        score, matches = score_for_category(tender, category)
        result[category] = {"score": score, "mots_cles_matches": matches}
    return result


def best_category(score_details: dict) -> tuple[str | None, int]:
    """Retourne la catégorie au meilleur score, et ce score."""
    best_cat, best_score = None, 0
    for cat, data in score_details.items():
        if data["score"] > best_score:
            best_cat, best_score = cat, data["score"]
    return best_cat, best_score