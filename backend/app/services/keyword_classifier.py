from .keyword_matcher import match_keywords
from app.schemas.sotradies import SotradiesRaw
from types import SimpleNamespace as _SimpleNamespace

def score_for_category(tender: SotradiesRaw, category: str, dynamic_categories: dict, dynamic_exclusions: list[str]) -> tuple[int, list[str]]:
    """Calcule le score d'une annonce pour une catégorie précise."""
    text = (tender.objet or "") + " " + (tender.categorie or "")
    
    # 1. Vérifie si on doit exclure (mots interdits)
    if match_keywords(text, dynamic_exclusions):
        
        return 0, []
    
    # 2. Cherche les mots-clés de la catégorie
    cat_data = dynamic_categories.get(category, {})
    keywords = cat_data.get("keywords", [])
    matches = match_keywords(text, keywords)
    
    if not matches:
        return 0, []
    
    # 3. Score simple : 60 points pour le 1er mot, 15 points par mot suivant
    score = min(100, 60 + 15 * (len(matches) - 1))
    return score, matches

def score_all_categories(tender: SotradiesRaw, dynamic_categories: dict, dynamic_exclusions: list[str]) -> dict:
    """Lance le score sur toutes les catégories du client."""
    result = {}
    for category in dynamic_categories:
        score, matches = score_for_category(tender, category, dynamic_categories, dynamic_exclusions)
        result[category] = {"score": score, "mots_cles_matches": matches}
    return result

def needs_ai_fallback(tender, score_details: dict, dynamic_categories: dict, dynamic_exclusions: list[str]) -> bool:
    """Décide si on a besoin de l'IA (si aucun mot-clé n'a été trouvé)."""
    # Si on a déjà trouvé un mot-clé, pas besoin d'IA
    if any(d["score"] > 0 for d in score_details.values()):
        return False
    # Si c'est une annonce exclue, pas besoin d'IA
    text = tender.objet or ""
    if match_keywords(text, dynamic_exclusions):
        return False
    # Sinon, on demande à l'IA
    return True 

def first_matching_keyword(text, keywords):
    """
    Retourne le premier mot-clé trouvé dans le texte, sinon None.
    Utilise la même logique (français + arabe) que le scoring.
    """
    # Tolère l'ordre inverse des arguments : (keywords, text)
    if isinstance(text, (list, tuple, set)) and isinstance(keywords, str):
        text, keywords = keywords, text

    cleaned = [str(k).strip() for k in (keywords or []) if str(k).strip()]
    if not text or not cleaned:
        return None

    fake_tender = _SimpleNamespace(objet=str(text), categorie=None)
    fake_categories = {"_RECHERCHE": {"keywords": cleaned, "marques": []}}

    _score, matches = score_for_category(
        fake_tender, "_RECHERCHE", fake_categories, []
    )
    return matches[0] if matches else None