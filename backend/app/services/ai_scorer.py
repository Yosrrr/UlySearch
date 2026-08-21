"""
Layer 4 — Tier 2 : scoring assisté par IA (modèle local Qwen2.5 3B via
Ollama), utilisé UNIQUEMENT en filet de sécurité sur les cas ambigus.

Les catégories viennent de la configuration admin (DB), pas de constantes
statiques.
"""
from app.services.local_llm_client import call_local_llm_json


def score_with_ai(
    objet: str,
    categorie_site: str | None,
    dynamic_categories: dict,
) -> dict:
    """Score un marché ambigu via IA locale, avec catégories dynamiques."""
    category_names = list(dynamic_categories.keys()) if dynamic_categories else []

    all_brands: list[str] = []
    for cat_data in (dynamic_categories or {}).values():
        all_brands.extend(cat_data.get("marques", []) or [])
    brands_unique = sorted(set(all_brands))
    brands_str = f" (marques {', '.join(brands_unique)})" if brands_unique else ""

    if not category_names:
        print("[ai_scorer] Aucune catégorie configurée — impossible de scorer via IA.")
        return {
            "pertinent": False,
            "categorie": None,
            "score": 0,
            "raison": "Aucune catégorie configurée en administration",
        }

    categories_list = ", ".join(category_names)

    system_prompt = f"""Tu aides à trier des appels d'offres publics tunisiens pour une société de vente/location de matériel roulant, engins TP et manutention{brands_str}.

Catégories possibles :
- {categories_list}

Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, exactement dans ce format :
{{"pertinent": true, "categorie": "NOM_CATEGORIE", "score": 75, "raison": "explication courte"}}
Si le marché n'est pas pertinent : {{"pertinent": false, "categorie": null, "score": 0, "raison": "explication courte"}}

La valeur de "categorie" doit être EXACTEMENT l'un des noms listés ci-dessus, ou null.
"""

    user_prompt = (
        f"Objet du marché : {objet}\n"
        f"Catégorie déclarée sur le site : {categorie_site or 'non précisée'}"
    )
    result = call_local_llm_json(system_prompt, user_prompt)

    if result is None:
        print("[ai_scorer] Échec de l'appel IA locale, marché non retenu par défaut.")
        return {
            "pertinent": False,
            "categorie": None,
            "score": 0,
            "raison": "Erreur technique IA (locale)",
        }

    try:
        result["score"] = int(result.get("score", 0))
    except (ValueError, TypeError):
        result["score"] = 0

    # Rejette une catégorie inventée par le modèle
    cat = result.get("categorie")
    if cat is not None and cat not in category_names:
        result["categorie"] = None
        if result.get("pertinent"):
            result["pertinent"] = False
            result["score"] = 0
            result["raison"] = (
                (result.get("raison") or "")
                + " | catégorie IA hors liste configurée"
            ).strip(" |")

    return result