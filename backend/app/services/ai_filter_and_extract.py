"""
Layer 4+6 : extraction IA locale.

Cette couche reçoit un texte contenant les métadonnées du marché
(objet, acheteur, dates, source...) et éventuellement le texte de détail.

Règles importantes :
- ne jamais inventer les chiffres, montants, dates, budget, cautionnement ;
- générer au minimum une description depuis les métadonnées disponibles ;
- rejeter toute catégorie inventée hors configuration admin.
"""

import re
from datetime import date

from dateutil import parser as date_parser

from app.services.local_llm_client import call_local_llm_json


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
        cleaned = (
            str(raw)
            .replace("\u202f", "")  # espace fine insécable
            .replace("\xa0", "")    # espace insécable
            .replace(" ", "")
            .replace("DT", "")
            .replace("TND", "")
            .replace(",", ".")
            .strip()
        )
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _normalize_whitespace(text: str | None) -> str:
    return " ".join((text or "").split())


def _extract_metadata_value(raw_text: str, labels: list[str]) -> str | None:
    """
    Extrait une valeur depuis un dump texte.

    Exemples attendus :
    - Objet : ...
    - Acheteur : ...
    - Date limite : ...
    """
    for label in labels:
        pattern = rf"(?im)^\s*{re.escape(label)}\s*[:：]\s*(.+?)\s*$"
        match = re.search(pattern, raw_text or "")
        if match:
            value = _normalize_whitespace(match.group(1))
            if value:
                return value
    return None


def _fallback_description_from_text(raw_text: str) -> str | None:
    """
    Génère une description minimale depuis les métadonnées du dump.

    Utile surtout pour TUNEPS : l'API publique donne déjà objet + acheteur
    + date limite, même si le détail HTML n'est pas encore exploité.
    """
    if not raw_text or not raw_text.strip():
        return None

    objet = _extract_metadata_value(
        raw_text,
        [
            "Objet",
            "Objet du marché",
            "Titre",
            "Intitulé",
            "Intitule",
        ],
    )

    acheteur = _extract_metadata_value(
        raw_text,
        [
            "Acheteur",
            "Acheteur public",
            "Organisme",
            "Institution",
        ],
    )

    date_limite = _extract_metadata_value(
        raw_text,
        [
            "Date limite",
            "Date limite de réception",
            "Date limite de reception",
            "Deadline",
        ],
    )

    source = _extract_metadata_value(raw_text, ["Source"])

    # Fallback si le dump n'a pas de label clair.
    if not objet:
        for line in raw_text.splitlines():
            clean = _normalize_whitespace(line)
            if len(clean) > 20 and ":" not in clean[:15]:
                objet = clean
                break

    if not objet:
        return None

    parts = [f"Cet appel d'offres concerne {objet}."]

    if acheteur:
        parts.append(f"L'acheteur public est {acheteur}.")

    if date_limite:
        parts.append(f"La date limite de réception des offres est {date_limite}.")
    elif source:
        parts.append(f"L'avis provient de la source {source}.")

    return " ".join(parts)


def _empty_with_description(raw_text: str, raison: str) -> dict:
    result = dict(_EMPTY_RESULT)
    result["raison"] = raison
    result["description_detaillee"] = (
        _fallback_description_from_text(raw_text)
        or "Description non disponible à partir des métadonnées fournies."
    )
    return result


def _build_system_prompt(dynamic_categories: dict) -> str:
    category_names = list(dynamic_categories.keys())

    all_brands: list[str] = []
    for cat_data in dynamic_categories.values():
        all_brands.extend(cat_data.get("marques", []) or [])

    brands_unique = sorted(set(all_brands))
    brands_str = f" (marques {', '.join(brands_unique)})" if brands_unique else ""

    return f"""Tu structures des appels d'offres publics tunisiens pour une société de vente/location de matériel roulant, engins TP et manutention{brands_str}.

Catégories possibles : {", ".join(category_names)}

Le texte fourni contient les métadonnées de l'offre (objet, acheteur, dates, source), puis éventuellement le texte brut de la page de détail.

Réponds UNIQUEMENT en JSON strict, sans aucun texte autour, avec exactement ces clés :
{{
  "pertinent": true ou false,
  "categorie": "UNE_DES_CATEGORIES_CI_DESSUS" ou null,
  "score": 0 à 100,
  "raison": "explication courte du score/de la catégorie",
  "description": "description claire de l'appel d'offres, 1 à 2 phrases en français",
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

Règles strictes :
- N'invente jamais un chiffre, une date, un budget, un cautionnement, une durée ou un lieu absent du texte : mets null.
- En revanche, "description" doit TOUJOURS être remplie si l'objet du marché est présent.
- Si le texte de détail est absent, limité ou protégé par abonnement, rédige "description" uniquement à partir des métadonnées disponibles : objet, acheteur, source, date limite.
- La valeur de "categorie" doit être exactement l'une des catégories listées ci-dessus, ou null.
"""


def filter_and_extract(raw_txt_content: str, dynamic_categories: dict) -> dict:
    """
    Prend le contenu complet du dump texte et retourne un dict prêt à stocker.

    Même si l'IA échoue ou retourne description=null, une description minimale
    est générée depuis les métadonnées si possible.
    """
    if not raw_txt_content or not raw_txt_content.strip():
        return dict(_EMPTY_RESULT)

    dynamic_categories = dynamic_categories or {}
    category_names = list(dynamic_categories.keys())
    fallback_description = _fallback_description_from_text(raw_txt_content)

    if not category_names:
        return _empty_with_description(
            raw_txt_content,
            "Aucune catégorie configurée en administration",
        )

    system_prompt = _build_system_prompt(dynamic_categories)
    data = call_local_llm_json(system_prompt, raw_txt_content[:4000])

    if data is None:
        print("[ai_filter_and_extract] Échec de l'appel IA locale.")
        return _empty_with_description(
            raw_txt_content,
            "Erreur technique IA (locale)",
        )

    if not isinstance(data, dict):
        return _empty_with_description(
            raw_txt_content,
            "Réponse IA invalide",
        )

    categorie = data.get("categorie")
    pertinent = bool(data.get("pertinent"))

    try:
        score = int(data.get("score", 0) or 0)
    except (ValueError, TypeError):
        score = 0

    score = max(0, min(100, score))

    # Si l'IA invente une catégorie, on rejette le verdict de pertinence.
    # La description reste utilisable.
    if categorie not in category_names:
        if pertinent:
            print(
                f"[ai_filter_and_extract] Catégorie IA hors configuration : "
                f"{categorie!r}. Résultat rejeté."
            )
        categorie = None
        pertinent = False
        score = 0

    description = data.get("description") or fallback_description

    if not description:
        description = "Description non disponible à partir des métadonnées fournies."

    return {
        "pertinent": pertinent,
        "categorie": categorie,
        "score": score,
        "raison": data.get("raison", ""),
        "description_detaillee": description,
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