"""
Onboarding IA — génère une configuration complète :
- catégories + mots-clés + marques
- exclusions
- sites web pertinents à surveiller

L'IA PROPOSE, l'humain VALIDE. Rien n'est écrit en base
tant que l'admin n'a pas cliqué sur "Valider".
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_admin_or_superadmin
from app.services.local_llm_client import call_local_llm_json


router = APIRouter(prefix="/admin/ai-suggest", tags=["admin-ai"])


FORBIDDEN_EXCLUSIONS = {
    "véhicule", "vehicule", "travaux", "service", "services",
    "fourniture", "fournitures", "acquisition", "achat",
    "marché", "marche", "appel", "offre", "offres",
    "maintenance", "entretien", "réparation", "reparation",
    "projet", "étude", "etude", "construction",
    "remplacement", "rénovation", "renovation",  # ← AJOUT
    "installation", "mise en service",
}


MAX_CATEGORIES = 10
MAX_KEYWORDS_PER_CATEGORY = 50
MAX_BRANDS = 30
MAX_EXCLUSIONS = 20
MAX_SITES = 10


class SuggestRequest(BaseModel):
    description: str


class SuggestedCategory(BaseModel):
    id: str
    label: str
    keywords: list[str]
    marques: list[str]


class SuggestedSite(BaseModel):
    nom: str
    url: str
    description: str


class SuggestResponse(BaseModel):
    categories: list[SuggestedCategory]
    exclusion_keywords: list[str]
    sites: list[SuggestedSite]
    warnings: list[str]


SYSTEM_PROMPT = """Tu génères une configuration de veille pour des appels d'offres.

RÈGLES ABSOLUES :
- Maximum 3 à 5 catégories (PAS PLUS)
- Chaque catégorie = un TYPE DE PRODUIT concret
- Les mots-clés = les NOMS DES PRODUITS (1 à 3 mots max)
- PAS de doublons entre catégories
- Inclure des termes en arabe tunisien

Pour les SITES, inclure TOUJOURS ces plateformes tunisiennes :
- ONMP : https://www.marchespublics.gov.tn/fr/appels-doffres
- TUNEPS : https://www.tuneps.tn/portail/offres
- Tunisie Marchés : https://www.tunisiemarches.com
- ATFP : https://www.atfp.tn (formation professionnelle)
- HAICOP : https://www.haicop.gov.tn (haute instance commande publique)

Et ajouter des sites INTERNATIONAUX pertinents selon le secteur :
- TED Europa : https://ted.europa.eu (marchés européens)
- DGMARKET : https://www.dgmarket.com (Banque Mondiale)
- BAD : https://www.afdb.org/fr/projects-and-operations/procurement (Banque Africaine)
- UNDP : https://procurement-notices.undp.org (Nations Unies)

Réponds UNIQUEMENT en JSON :
{
  "categories": [
    {
      "id": "NOM_COURT_MAJUSCULES",
      "label": "Nom court",
      "keywords": ["produit1", "produit2"],
      "marques": ["MARQUE1"]
    }
  ],
  "exclusion_keywords": ["terme hors secteur"],
  "sites": [
    {
      "nom": "Nom",
      "url": "https://...",
      "description": "Description"
    }
  ]
}

ATTENTION : ne génère PAS de catégories comme "contrats publics", "administration", "rénovation", "maintenance générale". Ce ne sont PAS des produits."""


def _clean_suggestion(data: dict) -> tuple[dict, list[str]]:
    """Nettoie et valide la suggestion de l'IA."""
    warnings = []

    categories = data.get("categories", [])
    exclusions = data.get("exclusion_keywords", [])
    sites = data.get("sites", [])

    # Catégories
    if len(categories) > MAX_CATEGORIES:
        categories = categories[:MAX_CATEGORIES]
        warnings.append(f"Tronqué à {MAX_CATEGORIES} catégories")

    cleaned_categories = []
    for cat in categories:
        cat_id = (cat.get("id") or "").upper().replace(" ", "_").replace("-", "_")
        if not cat_id:
            continue

        keywords = [
            str(kw).strip().lower().strip("\"'")
            for kw in (cat.get("keywords") or [])
            if str(kw).strip()
        ]
        keywords = list(dict.fromkeys(keywords))[:MAX_KEYWORDS_PER_CATEGORY]

        marques = [
            str(m).strip()
            for m in (cat.get("marques") or [])
            if str(m).strip()
        ]
        marques = list(dict.fromkeys(marques))[:MAX_BRANDS]

        cleaned_categories.append({
            "id": cat_id,
            "label": cat.get("label") or cat_id.replace("_", " ").title(),
            "keywords": keywords,
            "marques": marques,
        })

    # Exclusions
    cleaned_exclusions = []
    for kw in exclusions:
        kw_clean = str(kw).strip().lower()
        if not kw_clean:
            continue
        if kw_clean in FORBIDDEN_EXCLUSIONS:
            warnings.append(f"Exclusion trop générique retirée : '{kw_clean}'")
            continue
        cleaned_exclusions.append(kw_clean)
    cleaned_exclusions = list(dict.fromkeys(cleaned_exclusions))[:MAX_EXCLUSIONS]

    # Sites
    cleaned_sites = []
    seen_urls = set()
    for site in sites:
        url = (site.get("url") or "").strip()
        nom = (site.get("nom") or "").strip()
        desc = (site.get("description") or "").strip()

        if not url or not nom:
            continue
        if not url.startswith("http"):
            url = "https://" + url
        if url in seen_urls:
            continue

        seen_urls.add(url)
        cleaned_sites.append({
            "nom": nom,
            "url": url,
            "description": desc,
        })
    cleaned_sites = cleaned_sites[:MAX_SITES]

    return {
        "categories": cleaned_categories,
        "exclusion_keywords": cleaned_exclusions,
        "sites": cleaned_sites,
    }, warnings


@router.post("", response_model=SuggestResponse)
def suggest_configuration(
    payload: SuggestRequest,
    user=Depends(require_admin_or_superadmin),
):
    """
    Génère une suggestion complète : catégories + exclusions + sites.
    L'IA propose, l'admin valide. Rien n'est modifié en base.
    """
    description = payload.description.strip()

    if not description or len(description) < 10:
        raise HTTPException(400, "La description doit contenir au moins 10 caractères.")

    if len(description) > 2000:
        raise HTTPException(400, "La description ne doit pas dépasser 2000 caractères.")

    result = call_local_llm_json(
        SYSTEM_PROMPT,
        f"Description de l'activité du client :\n\n{description}",
    )

    if result is None:
        raise HTTPException(503, "Le modèle IA n'est pas disponible. Vérifiez qu'Ollama est démarré.")

    if not isinstance(result, dict):
        raise HTTPException(500, "Réponse IA invalide.")

    cleaned, warnings = _clean_suggestion(result)

    if not cleaned["categories"]:
        raise HTTPException(422, "L'IA n'a pas pu générer de catégories. Essayez une description plus détaillée.")

    return SuggestResponse(
        categories=[SuggestedCategory(**cat) for cat in cleaned["categories"]],
        exclusion_keywords=cleaned["exclusion_keywords"],
        sites=[SuggestedSite(**site) for site in cleaned["sites"]],
        warnings=warnings,
    )
    
@router.post("/public", response_model=SuggestResponse)
def suggest_configuration_public(payload: SuggestRequest):
    """Version publique — pas d'auth, utilisée par le formulaire d'inscription."""
    # Même logique que suggest_configuration, sans le Depends(auth)
    description = payload.description.strip()
    if not description or len(description) < 10:
        raise HTTPException(400, "Description trop courte.")
    if len(description) > 2000:
        raise HTTPException(400, "Description trop longue.")

    result = call_local_llm_json(SYSTEM_PROMPT, f"Activité :\n\n{description}")
    if result is None:
        raise HTTPException(503, "IA indisponible.")
    if not isinstance(result, dict):
        raise HTTPException(500, "Réponse invalide.")

    cleaned, warnings = _clean_suggestion(result)
    if not cleaned["categories"]:
        raise HTTPException(422, "Pas de catégories générées.")

    return SuggestResponse(
        categories=[SuggestedCategory(**c) for c in cleaned["categories"]],
        exclusion_keywords=cleaned["exclusion_keywords"],
        sites=[SuggestedSite(**s) for s in cleaned["sites"]],
        warnings=warnings,
    )