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

    if needs_ai_fallback(
        tender, score_details, dynamic_categories, dynamic_exclusions
    ):
        print(f"[scoring] Cas ambigu détecté, appel IA -> '{tender.objet[:60]}'")
        ai_result = score_with_ai(
            tender.objet,
            getattr(tender, "categorie", None),
            dynamic_categories,
        )
        categorie_ia = ai_result.get("categorie")

        if ai_result.get("pertinent") and categorie_ia in score_details:
            score_details[categorie_ia] = {
                "score": ai_result.get("score", 0),
                "mots_cles_matches": [],
                "methode": "ia",
                "raison_ia": ai_result.get("raison", ""),
            }
        else:
            print(
                f"[scoring] IA a jugé non pertinent -> '{tender.objet[:60]}' "
                f"(raison: {ai_result.get('raison', 'non précisée')})"
            )
    else:
        print(
            f"[scoring] Pas assez ambigu pour justifier l'IA -> '{tender.objet[:60]}'"
        )

    return score_details