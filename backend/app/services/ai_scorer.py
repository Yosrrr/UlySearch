"""
Layer 4 — Tier 2 : scoring assisté par IA (Google Gemini, niveau gratuit),
utilisé UNIQUEMENT en filet de sécurité sur les cas ambigus.
"""
import json

from google import genai

from app.core.config import settings

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """Tu aides à trier des appels d'offres publics tunisiens pour une société de vente/location de matériel roulant, engins TP et manutention (marques IVECO, CASE, HAMM, Wirtgen, Kleemann, Schwing Stetter, Hyster, Otokar, ALMIG, Himoinsa).

Catégories possibles :
- MATERIEL_ROULANT, ENGINS_TP, MANUTENTION, ENGINS_SPECIAUX, GROUPES_ELECTROGENES

Réponds UNIQUEMENT en JSON strict, sans aucun texte autour :
{"pertinent": true|false, "categorie": "NOM_CATEGORIE"|null, "score": 0-100, "raison": "..."}
"""


def score_with_ai(objet: str, categorie_site: str | None) -> dict:
    try:
        response = _client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=f"Objet du marché : {objet}\n"
                     f"Catégorie déclarée sur le site : {categorie_site or 'non précisée'}",
            config={"system_instruction": SYSTEM_PROMPT, "temperature": 0},
        )
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"[ai_scorer] Échec de l'appel IA, marché non retenu par défaut : {e}")
        return {"pertinent": False, "categorie": None, "score": 0, "raison": "Erreur technique IA"}