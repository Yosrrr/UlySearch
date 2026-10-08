"""
Rapprochement flou entre l'acheteur d'un marché scrapé et la liste
des acheteurs connus Sotradies (Layer 5).

Déterministe, sans IA — rapidfuzz uniquement.

Le matching repose sur deux contrôles :
1. similarité globale du nom ;
2. similarité du ou des mots distinctifs, pour éviter les faux positifs
   du type "Commune de Sfax" vs "Commune de Soukra".
"""
from rapidfuzz import fuzz
from unidecode import unidecode

from app.core.database import SessionLocal
from app.models.known_buyer import KnownBuyer

GLOBAL_MATCH_THRESHOLD = 85
DISTINCTIVE_WORD_THRESHOLD = 70

STOPWORDS = {
    "de", "des", "du", "la", "le", "les", "l", "et", "d",
    "municipalite", "municipalité", "commune", "office", "national",
    "regional", "régional", "commissariat", "societe", "société",
    "agence", "centre", "direction", "generale", "générale",
}


def _normalize(text: str) -> str:
    return unidecode(text or "").lower().strip()


def _distinctive_words(text: str) -> list[str]:
    words = _normalize(text).replace("'", " ").split()
    distinctive = [w for w in words if w not in STOPWORDS and len(w) > 2]
    return distinctive or words


def _distinctive_similarity(a: str, b: str) -> float:
    words_a = _distinctive_words(a)
    words_b = _distinctive_words(b)

    if not words_a or not words_b:
        return 0.0

    joined_a = " ".join(sorted(words_a))
    joined_b = " ".join(sorted(words_b))

    return fuzz.token_sort_ratio(joined_a, joined_b)


def find_matching_buyer(
    acheteur_scrape: str,
    known_buyers: list[KnownBuyer] | None = None,
) -> KnownBuyer | None:
    """
    Retourne le KnownBuyer correspondant dans la liste FOURNIE, sinon None.

    Isolation multi-tenant : cette fonction ne lit jamais la base elle-même.
    L'appelant doit fournir la liste des acheteurs d'UNE seule entreprise.
    """
    if not known_buyers:
        return None

    target = _normalize(acheteur_scrape)
    if not target:
        return None

    candidates: list[tuple[str, KnownBuyer]] = []
    for kb in known_buyers:
        candidates.append((kb.nom_acheteur, kb))
        if kb.variantes:
            for variante in kb.variantes.split(";"):
                variante = variante.strip()
                if variante:
                    candidates.append((variante, kb))

    best_score = 0
    best_kb = None
    for candidate_name, kb in candidates:
        global_score = fuzz.token_sort_ratio(target, _normalize(candidate_name))
        if global_score < GLOBAL_MATCH_THRESHOLD:
            continue

        distinctive_score = _distinctive_similarity(acheteur_scrape, candidate_name)
        if distinctive_score < DISTINCTIVE_WORD_THRESHOLD:
            continue

        if global_score > best_score:
            best_score = global_score
            best_kb = kb

    return best_kb  


_UNKNOWN_BUYERS = {"", "non precise", "non precisee", "inconnu", "n/a", "-"}


def match_buyer(
    acheteur_scrape: str,
    company_id: int | None = None,
) -> str | None:
    """
    Retourne "Oui", "Non" ou None.

    Isolation multi-tenant : sans company_id, aucune recherche n'est faite.
    On ne compare jamais un acheteur à la liste d'une autre entreprise.
    """
    if company_id is None:
        return None
    if _normalize(acheteur_scrape) in _UNKNOWN_BUYERS:
        return None

    db = SessionLocal()
    try:
        known_buyers = (
            db.query(KnownBuyer)
            .filter(KnownBuyer.company_id == company_id)
            .all()
        )
    finally:
        db.close()

    if not known_buyers:
        return None

    best_kb = find_matching_buyer(acheteur_scrape, known_buyers)
    return best_kb.client_sotradies if best_kb else None
def match_buyer_detail(
    acheteur_scrape: str,
    company_id: int | None = None,
) -> tuple[str | None, str | None]:
    """
    Retourne (statut client, nom de l'acheteur connu), ou (None, None).
    Même règle d'isolation : company_id obligatoire.
    """
    if company_id is None:
        return None, None
    if _normalize(acheteur_scrape) in _UNKNOWN_BUYERS:
        return None, None

    db = SessionLocal()
    try:
        known_buyers = (
            db.query(KnownBuyer)
            .filter(KnownBuyer.company_id == company_id)
            .all()
        )
    finally:
        db.close()

    best_kb = find_matching_buyer(acheteur_scrape, known_buyers) if known_buyers else None
    if not best_kb:
        return None, None
    return best_kb.client_sotradies, best_kb.nom_acheteur
