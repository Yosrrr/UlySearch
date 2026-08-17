"""
Layer 4 — Tier 2 : scoring assisté par IA (modèle local Qwen2.5 3B via
Ollama), utilisé UNIQUEMENT en filet de sécurité sur les cas ambigus.
"""
from app.services.local_llm_client import call_local_llm_json

SYSTEM_PROMPT = """Tu aides à trier des appels d'offres publics tunisiens pour une société de vente/location de matériel roulant, engins TP et manutention (marques IVECO, CASE, HAMM, Wirtgen, Kleemann, Schwing Stetter, Hyster, Otokar, ALMIG, Himoinsa).
Catégories possibles :
- MATERIEL_ROULANT, ENGINS_TP, MANUTENTION, ENGINS_SPECIAUX, GROUPES_ELECTROGENES
Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, exactement dans ce format :
{"pertinent": true, "categorie": "NOM_CATEGORIE", "score": 75, "raison": "explication courte"}
Si le marché n'est pas pertinent : {"pertinent": false, "categorie": null, "score": 0, "raison": "explication courte"}
"""


def score_with_ai(objet: str, categorie_site: str | None) -> dict:
    user_prompt = (
        f"Objet du marché : {objet}\n"
        f"Catégorie déclarée sur le site : {categorie_site or 'non précisée'}"
    )
    result = call_local_llm_json(SYSTEM_PROMPT, user_prompt)

    if result is None:
        print("[ai_scorer] Échec de l'appel IA locale, marché non retenu par défaut.")
        return {"pertinent": False, "categorie": None, "score": 0, "raison": "Erreur technique IA (locale)"}

    # Sécurise les types au cas où le modèle 3B renvoie un score en texte ("75" au lieu de 75)
    try:
        result["score"] = int(result.get("score", 0))
    except (ValueError, TypeError):
        result["score"] = 0

    return result