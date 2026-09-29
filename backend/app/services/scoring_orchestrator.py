"""
Orchestre le scoring complet d'un marché (Layer 4) :
Tier 1 (règles dynamiques) -> Tier 2 (IA, uniquement si ambigu).
Chaque score en base garde la trace de sa méthode ("regles" | "ia").
"""
from app.services.keyword_classifier import (
    score_all_categories,
    needs_ai_fallback,
)

from app.services.ai_scorer import score_with_ai


import hashlib as _hashlib
import json as _json

_AI_CALL_CACHE: dict[str, dict] = {}

def _categories_hash(dynamic_categories: dict) -> str:
    """Empreinte stable d'une configuration client pour le cache IA."""
    try:
        serialized = _json.dumps(dynamic_categories, sort_keys=True, ensure_ascii=False)
    except Exception:
        serialized = str(dynamic_categories)
    return _hashlib.md5(serialized.encode()).hexdigest()[:12]

_OBVIOUS_OFF_TOPIC = {
    "alimentation", "denree", "nourriture", "viande", "volaille",
    "assurance", "avocat", "juridique", "architecte", "formation professionnelle",
    "mobilier bureau", "papeterie", "consommable bureautique",
    "hebergement", "seminaire", "evenement", "billet avion",
    "nettoyage voirie", "dechets menagers",
}


def _is_obvious_off_topic(objet: str, categories: dict) -> bool:
    """
    Vrai si l'objet contient un terme éliminatoire ET qu'aucune catégorie
    ne couvre ce domaine. Évite les appels IA évidents.
    """
    from app.services.keyword_scorer import normalize_text
    normalized = normalize_text(objet)
    return any(
        term in normalized
        for term in _OBVIOUS_OFF_TOPIC
        if term not in " ".join(
            " ".join(str(k) for k in (cat.get("keywords") or []))
            for cat in categories.values()
            if isinstance(cat, dict)
        )
    )
def score_tender_full(
    tender,
    dynamic_categories: dict,
    dynamic_exclusions: list[str],
) -> dict:
    score_details = score_all_categories(
        tender, dynamic_categories, dynamic_exclusions
    )
    for cat in score_details:
        score_details[cat]["methode"] = "regles"

    if not needs_ai_fallback(
        tender, score_details, dynamic_categories, dynamic_exclusions
    ):
        print(
            f"[scoring] Pas assez ambigu pour justifier l'IA -> '{tender.objet[:60]}'"
        )
        return score_details
    if _is_obvious_off_topic(tender.objet, dynamic_categories):
        print(f"[scoring] Hors secteur évident, IA ignorée -> '{tender.objet[:60]}'")
        return score_details

    # Clé de cache : objet + empreinte des catégories du client
    cache_key = f"{tender.objet[:200]}|{_categories_hash(dynamic_categories)}"

    if cache_key in _AI_CALL_CACHE:
        # Résultat déjà calculé pour ce client sur cette offre
        return _AI_CALL_CACHE[cache_key]

    print(f"[scoring] Cas ambigu détecté, appel IA -> '{tender.objet[:60]}'")
    ai_result = score_with_ai(
        tender.objet,
        getattr(tender, "categorie", None),
        dynamic_categories,
    )
    categorie_ia = ai_result.get("categorie")
    ai_score = max(0, min(100, int(ai_result.get("score", 0) or 0)))

    if (
        ai_result.get("pertinent") is True
        and categorie_ia in score_details
        and ai_score >= 50
    ):
        score_details[categorie_ia] = {
            "score": ai_score,
            "mots_cles_matches": [],
            "methode": "ia",
            "raison_ia": ai_result.get("raison", ""),
        }
    else:
        print(
            f"[scoring] IA a jugé non pertinent -> '{tender.objet[:60]}' "
            f"(raison: {ai_result.get('raison', 'non précisée')})"
        )

    _AI_CALL_CACHE[cache_key] = score_details
    return score_details