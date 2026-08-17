"""
Nettoie et structure le texte brut scrapé d'une page de détail de marché,
via le modèle local Qwen2.5 3B (Ollama) — même rôle qu'avant avec Gemini,
juste en local désormais.
"""
from datetime import date
from dateutil import parser as date_parser

from app.services.local_llm_client import call_local_llm_json

SYSTEM_PROMPT = """Tu extrais des informations structurées depuis le texte brut d'une page web d'un appel d'offres public tunisien (le menu et le pied de page du site sont inclus dans le texte — ignore-les complètement).
Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, avec exactement ces clés :
{
  "description": "résumé clair et concis de l'objet et du contexte du marché, 2 à 4 phrases, en français",
  "budget_detecte": nombre ou null,
  "duree_execution": "texte court, ex: '6 mois'" ou null,
  "montant_cautionnement": nombre ou null,
  "type_marche": "Fournitures" ou "Travaux" ou "Services" ou null,
  "procedure_passation": "texte court" ou null,
  "region_execution": "texte court" ou null,
  "date_debut_execution": "YYYY-MM-DD" ou null,
  "date_ouverture_offres": "YYYY-MM-DD" ou null,
  "lieu_ouverture_offres": "texte court" ou null,
  "caractere_prix": "Ferme" ou "Révisable" ou null
}
Les montants sont en dinars tunisiens, sans texte ni symbole. N'invente jamais une valeur absente du texte — mets null."""

_EMPTY_RESULT = {
    "description_detaillee": None,
    "budget_detecte": None,
    "duree_execution": None,
    "montant_cautionnement": None,
    "type_marche": None,
    "procedure_passation": None,
    "region_execution": None,
    "date_debut_execution": None,
    "date_ouverture_offres": None,
    "lieu_ouverture_offres": None,
    "caractere_prix": None,
}


def _safe_parse_date(raw) -> date | None:
    if not raw:
        return None
    try:
        return date_parser.parse(str(raw)).date()
    except Exception:
        return None


def _safe_float(raw) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def clean_and_structure(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return dict(_EMPTY_RESULT)

    # Un modèle 3B a une fenêtre de contexte plus limitée qu'un modèle
    # cloud — on tronque plus court qu'avant (6000 -> 3500) pour rester
    # dans une zone où Qwen reste fiable.
    data = call_local_llm_json(SYSTEM_PROMPT, raw_text[:3500])

    if data is None:
        print("[ai_detail_extractor] Échec du nettoyage IA locale.")
        return dict(_EMPTY_RESULT)

    return {
        "description_detaillee": data.get("description"),
        "budget_detecte": _safe_float(data.get("budget_detecte")),
        "duree_execution": data.get("duree_execution"),
        "montant_cautionnement": _safe_float(data.get("montant_cautionnement")),
        "type_marche": data.get("type_marche"),
        "procedure_passation": data.get("procedure_passation"),
        "region_execution": data.get("region_execution"),
        "date_debut_execution": _safe_parse_date(data.get("date_debut_execution")),
        "date_ouverture_offres": _safe_parse_date(data.get("date_ouverture_offres")),
        "lieu_ouverture_offres": data.get("lieu_ouverture_offres"),
        "caractere_prix": data.get("caractere_prix"),
    }