"""
Décision de pertinence d'un marché pour UN client — option B :
les mots-clés ET l'IA pèsent ensemble, aucune source ne décide seule.

0. Exclusion du client (objet + catégorie source, correspondance exacte) : rejet, sans IA.
1. Mots-clés du client cherchés dans l'objet, la catégorie source et la description,
   fautes de frappe tolérées (match_keyword). AUCUN mot-clé -> "non_retenu", sans appel IA.
   Si AI_RESCUE_ENABLED (configuration) : l'IA est tout de même consultée pour alimenter
   la file "a_verifier" (mots-clés manquants du client), jamais pour retenir.
2. Filtre IA contextuel (juger_marche) : catégorie et confiance (faible | moyenne | haute).
3. Matrice (_appliquer) :
     IA non pertinente / catégorie inconnue        -> ia_rejet (faux positif éliminé, raison visible)
     mot-clé dans la catégorie de l'IA + haute     -> 85, seul cas pouvant déclencher une alerte (seuil 70)
     mot-clé dans la catégorie de l'IA + moyenne   -> 65, retenu sans alerte
     mot-clé dans la catégorie de l'IA + faible    -> ia_rejet
     mot-clé dans une AUTRE catégorie + haute/moy. -> 65 sous la catégorie du mot-clé,
                                                      catégorie IA tracée (preuve "recategorisation")
     mot-clé dans une AUTRE catégorie + faible     -> ia_rejet
     aucun mot-clé (rattrapage activé)             -> a_verifier si haute, sinon ia_rejet ; jamais retenu
4. IA indisponible -> a_verifier, jamais mis en cache.

Le seuil de décision (configuration client) est appliqué par le pipeline.
"""
from __future__ import annotations
from app.services.keyword_matcher import match_keywords

import copy
import hashlib
import json
import logging
from collections import Counter, OrderedDict
from typing import Any
from app.services.text_normalizer import first_term, normalize_text
import re                                                                  # avec les imports
from app.core.config import settings
from app.services.ai_scorer import PROMPT_VERSION, juger_marche
from app.services.keyword_scorer import match_keyword

logger = logging.getLogger(__name__)

SCORE_HAUTE_AVEC_MOT_CLE = 85   # seul cas pouvant déclencher une alerte (seuil 70)
SCORE_RETENU_SANS_ALERTE = 65
METHODE_REGLES_SANS_IA = "regles_sans_ia"
SCORE_SANS_IA = 60
METHODE_EXCLUSION = "exclusion"
METHODE_IA = "ia"
METHODE_REJET = "ia_rejet"
METHODE_NON_RETENU = "non_retenu"
METHODE_A_VERIFIER = "a_verifier"
METHODE_A_EXAMINER = "a_examiner"

# Consulter l'IA sans aucun mot-clé (file "a_verifier"). Désactivé par défaut : sous
# l'option B une offre sans mot-clé n'est jamais retenue ; l'appel ne sert qu'à la
# revue humaine et représenterait ~95 % des appels IA.
AI_REVIEW_WITHOUT_KEYWORD: bool = bool(getattr(settings, "AI_RESCUE_ENABLED", False))

_CACHE_MAX = 2000
_AI_CALL_CACHE: "OrderedDict[str, dict]" = OrderedDict()
STATS: Counter = Counter()


def get_scoring_stats() -> dict:
    total = STATS["total"]
    data = dict(STATS)
    data["taux_appel_ia"] = round(STATS["appel_ia"] / total, 3) if total else 0.0
    return data


def reset_cache() -> None:
    _AI_CALL_CACHE.clear()


def _cache_get(key: str):
    value = _AI_CALL_CACHE.get(key)
    if value is None:
        return None
    _AI_CALL_CACHE.move_to_end(key)
    return copy.deepcopy(value)


def _cache_set(key: str, value: dict) -> None:
    _AI_CALL_CACHE[key] = copy.deepcopy(value)
    _AI_CALL_CACHE.move_to_end(key)
    while len(_AI_CALL_CACHE) > _CACHE_MAX:
        _AI_CALL_CACHE.popitem(last=False)


def _marche(tender: Any) -> dict:
    return {
        "objet": getattr(tender, "objet", None) or "",
        "acheteur": getattr(tender, "acheteur", None) or "",
        "categorie_site": getattr(tender, "categorie", None),
        "description": getattr(tender, "description_detaillee", None) or "",
        "type_marche": getattr(tender, "type_marche", None),
    }


def _client(categories: dict, exclusions: list[str], profil: str | None) -> dict:
    return {
        "profil": (profil or "").strip() or None,
        "categories": {
            cid: {
                "label": data.get("label") or cid,
                "keywords": data.get("keywords") or [],
                "marques": data.get("marques") or [],
            }
            for cid, data in categories.items()
        },
        "exclusions": list(exclusions),
    }


def _cle_cache(marche: dict, client: dict) -> str:
    serial = json.dumps(
        {"v": PROMPT_VERSION, "modele": getattr(settings, "OLLAMA_MODEL", ""), "marche": marche, "client": client},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def _uniforme(categories: dict, methode: str, **extra) -> dict:
    return {cid: {"score": 0, "mots_cles_matches": [], "methode": methode, **extra} for cid in categories}

def _indices(texte: str, categories: dict) -> dict[str, list[str]]:
    """Mots-clés présents par catégorie : union du matcher à racines (keyword_matcher, français +
    arabe) et du matcher tolérant aux fautes (keyword_scorer). Un mot-clé manqué par l'un est
    rattrapé par l'autre ; c'est l'IA qui tient la précision, un rappel large coûte 2 s d'IA."""
    result: dict[str, list[str]] = {}
    for cid, data in categories.items():
        mots = [k for k in (data.get("keywords") or []) if isinstance(k, str) and k.strip()]
        par_racine = set(match_keywords(texte, mots) or [])
        result[cid] = [k for k in mots if k in par_racine or match_keyword(texte, k) is not None]
    return result


def _decider(confiance: str | None, a_mot_cle: bool) -> int | None:
    """Score final, ou None si rejet. Fonction pure : l'IA seule (a_mot_cle=False) ne décide jamais."""
    if not a_mot_cle:
        return None
    if confiance == "haute":
        return SCORE_HAUTE_AVEC_MOT_CLE
    if confiance == "moyenne":
        return SCORE_RETENU_SANS_ALERTE
    return None


def _resultat(categories, cat, score, methode, mots, confiance, raison, **extra) -> dict:
    result = _uniforme(categories, METHODE_NON_RETENU)   # catégories perdantes : non retenues, jamais "ia"/"a_verifier"
    result[cat] = {
        "score": score,
        "mots_cles_matches": list(mots or []),
        "methode": methode,
        "mot_cle_present": True,
        "confiance_ia": confiance,
        "raison_ia": raison,
        **extra,
    }
    return result



def _appliquer(verdict: dict, categories: dict, indices: dict[str, list[str]]) -> dict:
    """Matrice de l'option B. indices = {categorie: [mots-clés trouvés]}."""
    raison = " ".join(str(verdict.get("raison") or "").split())
    confiance = str(verdict.get("confiance") or "").strip().lower() or None
    cat_ia = verdict.get("categorie")
    cats_mot_cle = [c for c, mots in (indices or {}).items() if mots]


    # "pertinent" s'il est fourni ; sinon la catégorie vaut décision (AUCUNE / None = rien ne convient).
    pertinent = verdict.get("pertinent")
    if pertinent is None:
        pertinent = cat_ia in categories
    if not pertinent or cat_ia not in categories:
        return _uniforme(categories, METHODE_REJET, raison_ia=raison, confiance_ia=confiance)

    if cat_ia in cats_mot_cle:                                   # accord mot-clé / IA
        score = _decider(confiance, True)
        if score is None:
            return _uniforme(categories, METHODE_REJET, confiance_ia=confiance,
                             raison_ia=f"Confiance IA {confiance or 'inconnue'} : non retenu malgré le mot-clé. {raison}")
        return _resultat(categories, cat_ia, score, METHODE_IA, indices[cat_ia], confiance, raison, preuve="regles_et_ia")

    if cats_mot_cle:                                             # mot-clé ailleurs : désaccord de catégorie
        if confiance == "faible":
            return _uniforme(categories, METHODE_REJET, confiance_ia=confiance,
                             raison_ia=f"Confiance IA faible : non retenu. {raison}")
        cat_regles = max(cats_mot_cle, key=lambda c: len(indices[c]))
        return _resultat(categories, cat_regles, SCORE_RETENU_SANS_ALERTE, METHODE_IA, indices[cat_regles],
                         confiance, raison, preuve="recategorisation", categorie_ia=cat_ia)

    methode = METHODE_A_EXAMINER if confiance == "haute" else METHODE_REJET

    return _uniforme(categories, methode, confiance_ia=confiance, categorie_ia=cat_ia,
                     raison_ia=f"Aucun mot-clé du client dans l'annonce : non retenu (l'IA seule ne décide pas). {raison}")


def score_tender_full(
    tender: Any,
    dynamic_categories: dict[str, Any],
    dynamic_exclusions: list[str],
    profil_client: str | None = None,
) -> dict:
    """Retourne {categorie: {score, mots_cles_matches, methode, ...}} pour UN client."""
    categories = {k: v for k, v in (dynamic_categories or {}).items() if isinstance(v, dict)}
    exclusions = [e for e in (dynamic_exclusions or []) if isinstance(e, str) and e.strip()]
    if not categories:
        return {}

    STATS["total"] += 1
    marche = _marche(tender)

    # 0. Exclusion : objet et catégorie source, correspondance exacte
    texte_titre = f"{marche['objet']} {marche['categorie_site'] or ''}"
    mot_exclu = first_term(texte_titre, exclusions)
    if mot_exclu:
        STATS["exclusion"] += 1
        return _uniforme(categories, METHODE_EXCLUSION, mot_exclusion=mot_exclu)

    # 1. Mots-clés (objet, catégorie source, description) puis porte : sans mot-clé, pas d'IA
    texte_complet = f"{texte_titre} {marche['description']}"
    mots_par_categorie = _indices(texte_complet, categories)
    if not any(mots_par_categorie.values()) and not AI_REVIEW_WITHOUT_KEYWORD:
        STATS["sans_mot_cle"] += 1
        return _uniforme(categories, METHODE_NON_RETENU, raison_ia="Aucun mot-clé du client dans l'annonce")

    if not getattr(settings, "LLM_ENABLED", False):
        STATS["ia_desactivee"] += 1
        cats_mot_cle = [c for c, mots in mots_par_categorie.items() if mots]
        if not cats_mot_cle:
            return _uniforme(categories, METHODE_NON_RETENU, raison_ia="Aucun mot-clé du client dans l'annonce")
        cat_mc = max(cats_mot_cle, key=lambda c: len(mots_par_categorie[c]))
        return _resultat(categories, cat_mc, SCORE_SANS_IA, METHODE_REGLES_SANS_IA, mots_par_categorie[cat_mc],
                         None, "IA désactivée : retenu sur mot-clé seul, contexte non vérifié", preuve="regles_seules")
    alias, categories_codees = _coder_categories(categories)

    client = _client(categories_codees, exclusions, profil_client)

    cle = _cle_cache(marche, client)
    cached = _cache_get(cle)
    if cached is not None:
        STATS["cache_hit"] += 1
        return cached

    # 2. Filtre contextuel IA
    STATS["appel_ia"] += 1
    verdict = _decoder_verdict(juger_marche(marche, client), alias, categories)

    # IA indisponible : à vérifier, jamais mis en cache
    if not verdict or verdict.get("erreur"):
        STATS["a_verifier"] += 1
        motif = (verdict or {}).get("raison") or "IA indisponible"
        logger.warning("[scoring] %s, décision provisoire : '%s'", motif, marche["objet"][:60])
        cats_mot_cle = [c for c, mots in mots_par_categorie.items() if mots]
        if not cats_mot_cle:
            return _uniforme(categories, METHODE_NON_RETENU,
                             raison_ia=f"{motif} ; aucun mot-clé du client : non retenu")
        cat_mc = max(cats_mot_cle, key=lambda c: len(mots_par_categorie[c]))
        return _resultat(categories, cat_mc, SCORE_SANS_IA, METHODE_A_VERIFIER, mots_par_categorie[cat_mc],
                         None, f"{motif} : retenu provisoirement sur mot-clé, contexte à confirmer au prochain run",
                         preuve="regles_seules", provisoire=True)
    # 3. Matrice
    result = _appliquer(verdict, categories, mots_par_categorie)
    if any(d["methode"] == METHODE_IA for d in result.values()):
        STATS["retenu"] += 1
    else:
        STATS["rejet"] += 1
    _cache_set(cle, result)
    return result
def _coder_categories(categories: dict) -> tuple[dict[str, str], dict]:
    """Codes neutres (C1, C2…) envoyés au modèle à la place des identifiants.

    Un identifiant comme FABRICATION_MATIER_PREMIERE est lu par un petit modèle comme
    « matières premières ». Un code ne porte aucun sens : le besoin reste défini par
    l'intitulé et les mots-clés. Sans intitulé, l'identifiant sert d'intitulé (ENGINS_TP).
    """
    alias = {f"C{i}": cid for i, cid in enumerate(categories, start=1)}
    codees = {code: {**categories[cid], "label": categories[cid].get("label") or cid} for code, cid in alias.items()}
    return alias, codees


def _decoder_verdict(verdict: Any, alias: dict[str, str], categories: dict) -> Any:
    """Ramène la catégorie du verdict à l'identifiant configuré (code, identifiant ou intitulé)
    et remplace les codes cités dans la raison par l'intitulé."""
    if not isinstance(verdict, dict):
        return verdict
    verdict = dict(verdict)
    brut = str(verdict.get("categorie") or "").strip()
    if brut in alias:
        verdict["categorie"] = alias[brut]
    elif brut and brut not in categories:
        voulu = normalize_text(brut)
        candidats = [cid for cid, d in categories.items()
                     if voulu and voulu in {normalize_text(cid), normalize_text(d.get("label") or "")}]
        if len(candidats) == 1:
            verdict["categorie"] = candidats[0]
    raison = str(verdict.get("raison") or "")
    for code, cid in alias.items():
        label = categories[cid].get("label") or cid
        raison = re.sub(rf"\b{code}\b", lambda _m, l=label: l, raison)
    verdict["raison"] = raison
    return verdict
