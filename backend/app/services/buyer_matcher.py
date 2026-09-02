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
    Retourne l'objet KnownBuyer correspondant si un rapprochement fiable
    est trouvé, sinon None.
    """
    close_db = False

    if known_buyers is None:
        db = SessionLocal()
        known_buyers = db.query(KnownBuyer).all()
        close_db = True
    else:
        db = None

    try:
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
            global_score = fuzz.token_sort_ratio(
                target,
                _normalize(candidate_name),
            )

            if global_score < GLOBAL_MATCH_THRESHOLD:
                continue

            distinctive_score = _distinctive_similarity(
                acheteur_scrape,
                candidate_name,
            )

            if distinctive_score < DISTINCTIVE_WORD_THRESHOLD:
                continue

            if global_score > best_score:
                best_score = global_score
                best_kb = kb

        return best_kb

    finally:
        if close_db and db is not None:
            db.close()


def match_buyer(acheteur_scrape: str) -> str | None:
    """
    Fonction historique utilisée par le pipeline.
    Retourne uniquement le statut client : "Oui", "Non" ou None.
    """
    best_kb = find_matching_buyer(acheteur_scrape)
    return best_kb.client_sotradies if best_kb else None


def match_buyer_detail(acheteur_scrape: str) -> tuple[str | None, str | None]:
    """
    Retourne le statut client ET le nom de l'acheteur connu matché.

    Exemple :
    ("Oui", "Société des Transports de Tunis")
    ("Non", "Office National de l'Assainissement")
    (None, None)
    """
    best_kb = find_matching_buyer(acheteur_scrape)

    if not best_kb:
        return None, None

    return best_kb.client_sotradies, best_kb.nom_acheteur