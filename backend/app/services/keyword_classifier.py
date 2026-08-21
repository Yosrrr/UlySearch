"""
Scoring de pertinence par mots-clés (Layer 4, Tier 1) — par catégorie,
avec assignation commerciale directement issue de la même table dynamique.
"""
from unidecode import unidecode
from rapidfuzz import fuzz
from app.schemas.sotradies import SotradiesRaw


def _normalize(text: str) -> str:
    return unidecode(text or "").lower()


def score_for_category(tender: SotradiesRaw, category: str, dynamic_categories: dict, dynamic_exclusions: list[str]) -> tuple[int, list[str]]:
    text = _normalize(tender.objet) + " " + _normalize(tender.categorie or "")

    if any(_normalize(kw) in text for kw in dynamic_exclusions):
        return 0, []

    category_data = dynamic_categories.get(category, {})
    keywords = category_data.get("keywords", [])
    matches = [kw for kw in keywords if _normalize(kw) in text]

    if not matches:
        return 0, []

    score = min(100, 60 + 15 * (len(matches) - 1))
    return score, matches


def score_all_categories(tender: SotradiesRaw, dynamic_categories: dict, dynamic_exclusions: list[str]) -> dict:
    """Retourne le détail complet du scoring, prêt à stocker dans score_details."""
    result = {}
    for category in dynamic_categories:
        score, matches = score_for_category(tender, category, dynamic_categories, dynamic_exclusions)
        result[category] = {"score": score, "mots_cles_matches": matches}
    return result


def best_category(score_details: dict) -> tuple[str | None, int]:
    """Retourne la catégorie au meilleur score, et ce score."""
    best_cat, best_score = None, 0
    for cat, data in score_details.items():
        if data["score"] > best_score:
            best_cat, best_score = cat, data["score"]
    return best_cat, best_score


MIN_FUZZY_FOR_AI = 55  # en dessous : trop éloigné, pas la peine de solliciter l'IA


def _best_fuzzy_score(text: str, dynamic_categories: dict) -> int:
    """Meilleure similarité floue entre l'objet du marché et n'importe quel
    mot-clé, toutes catégories confondues."""
    normalized_text = _normalize(text)
    best = 0
    for cat_data in dynamic_categories.values():
        for kw in cat_data.get("keywords", []):
            score = fuzz.partial_ratio(_normalize(kw), normalized_text)
            if score > best:
                best = score
    return best


def needs_ai_fallback(tender, score_details: dict, dynamic_categories: dict, dynamic_exclusions: list[str]) -> bool:
    """
    Cas ambigu = AUCUNE catégorie n'a matché par mots-clés exacts (Tier 1),
    ET ce n'est pas un cas d'exclusion déjà tranché avec confiance,
    ET il existe une ressemblance floue suffisante pour justifier l'IA.
    """
    if any(d["score"] > 0 for d in score_details.values()):
        return False  # une règle a déjà tranché avec confiance

    text = _normalize(tender.objet)
    if any(_normalize(kw) in text for kw in dynamic_exclusions):
        return False  # déjà identifié hors-secteur avec confiance, pas besoin d'IA

    return _best_fuzzy_score(tender.objet, dynamic_categories) >= MIN_FUZZY_FOR_AI