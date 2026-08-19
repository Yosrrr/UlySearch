"""
Layer 4+6 fusionnés : un seul appel au modèle local (Qwen2.5 3B / Ollama)
qui FILTRE l'offre (pertinent oui/non, catégorie, score) ET EXTRAIT ses
détails (description, budget, durée...) en une seule passe, à partir du
fichier .txt déjà sauvegardé (raw_dump.py).

Décision direction du 17/08/2026 : le modèle local traite directement le
texte brut complet, plutôt que le filtre par mots-clés suivi d'une
extraction IA séparée.
"""
from datetime import date
from dateutil import parser as date_parser

from app.services.local_llm_client import call_local_llm_json
from app.core.keywords import CATEGORIES

CATEGORY_NAMES = list(CATEGORIES.keys())

SYSTEM_PROMPT = f"""Tu tries et structures des appels d'offres publics tunisiens pour une société de vente/location de matériel roulant, engins TP et manutention (marques IVECO, CASE, HAMM, Wirtgen, Kleemann, Schwing Stetter, Hyster, Otokar, ALMIG, Himoinsa).

Catégories possibles : {", ".join(CATEGORY_NAMES)}

Le texte fourni contient les métadonnées de l'offre (objet, acheteur, dates) suivies du texte brut de la page de détail (peut être absent ou limité si la source est protégée par un abonnement — fais de ton mieux avec ce qui est disponible).

Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, avec exactement ces clés :
{{
  "pertinent": true ou false,
  "categorie": "UNE_DES_CATEGORIES_CI_DESSUS" ou null,
  "score": 0 à 100,
  "raison": "explication courte du score/de la catégorie",
  "description": "résumé clair de l'objet et du contexte, 2 à 4 phrases, en français, ou null si aucune information exploitable",
  "budget_detecte": nombre en dinars tunisiens ou null,
  "duree_execution": "texte court, ex: '6 mois'" ou null,
  "montant_cautionnement": nombre ou null,
  "type_marche": "Fournitures" ou "Travaux" ou "Services" ou null,
  "procedure_passation": "texte court" ou null,
  "region_execution": "texte court" ou null,
  "date_debut_execution": "YYYY-MM-DD" ou null,
  "date_ouverture_offres": "YYYY-MM-DD" ou null,
  "lieu_ouverture_offres": "texte court" ou null,
  "caractere_prix": "Ferme" ou "Révisable" ou null
}}
N'invente jamais une valeur absente du texte — mets null. Si le texte de détail indique explicitement qu'il n'est pas accessible (abonnement requis), base-toi uniquement sur l'objet/catégorie déclarée pour "pertinent"/"categorie"/"score", et mets "description" à null plutôt que d'inventer un résumé."""

_EMPTY_RESULT = {
    "pertinent": False,
    "categorie": None,
    "score": 0,
    "raison": "Erreur technique IA (locale)",
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


def filter_and_extract(raw_txt_content: str) -> dict:
    """Prend le contenu complet du fichier .txt (métadonnées + détail),
    retourne un dict prêt pour le scoring ET l'insertion en base."""
    if not raw_txt_content or not raw_txt_content.strip():
        return dict(_EMPTY_RESULT)

    # Fenêtre de contexte limitée du modèle 3B local — même précaution
    # que le reste du projet (ancien ai_detail_extractor.py tronquait à 3500).
    data = call_local_llm_json(SYSTEM_PROMPT, raw_txt_content[:4000])

    if data is None:
        print("[ai_filter_and_extract] Échec de l'appel IA locale.")
        return dict(_EMPTY_RESULT)

    categorie = data.get("categorie")
    if categorie not in CATEGORY_NAMES:
        categorie = None

    try:
        score = int(data.get("score", 0))
    except (ValueError, TypeError):
        score = 0

    return {
        "pertinent": bool(data.get("pertinent")),
        "categorie": categorie,
        "score": score,
        "raison": data.get("raison", ""),
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