"""Rapprochement flou entre l'acheteur d'un marché scrapé et la liste
des clients connus (Layer 5). Déterministe, pas d'IA — rapidfuzz uniquement.

⚠️ Piège identifié en test : les noms d'organismes publics tunisiens
partagent souvent une structure très proche ("Municipalité de X",
"Commissariat Régional de Y"), avec seul le nom de la ville qui change.
Un simple score de similarité globale (token_sort_ratio) peut donc
produire un FAUX POSITIF entre deux villes différentes. On exige donc
un second contrôle : le "mot distinctif" (le dernier mot significatif,
généralement le nom du lieu/de l'entité) doit lui aussi être proche.
"""
from rapidfuzz import fuzz, process
from unidecode import unidecode

from app.core.database import SessionLocal
from app.models.known_buyer import KnownBuyer

GLOBAL_MATCH_THRESHOLD = 85    # similarité globale minimum
DISTINCTIVE_WORD_THRESHOLD = 80  # similarité minimum sur le(s) mot(s) distinctif(s)

# Mots génériques très fréquents dans les noms d'acheteurs publics tunisiens,
# à ignorer pour identifier le(s) mot(s) réellement distinctif(s)
STOPWORDS = {
    "de", "des", "du", "la", "le", "les", "l", "et", "d",
    "municipalite", "municipalité", "commune", "office", "national",
    "regional", "régional", "commissariat", "societe", "société",
    "agence", "centre", "direction", "generale", "générale",
}


def _normalize(text: str) -> str:
    return unidecode(text or "").lower().strip()


def _distinctive_words(text: str) -> list[str]:
    """Retourne les mots du nom qui ne sont pas des termes génériques
    d'organisme public — typiquement le nom de la ville/entité."""
    words = _normalize(text).replace("'", " ").split()
    distinctive = [w for w in words if w not in STOPWORDS and len(w) > 2]
    return distinctive or words  # si tout est générique, on retombe sur tous les mots


def _distinctive_similarity(a: str, b: str) -> float:
    """Compare uniquement les mots distinctifs des deux noms."""
    words_a = _distinctive_words(a)
    words_b = _distinctive_words(b)
    if not words_a or not words_b:
        return 0.0
    joined_a = " ".join(sorted(words_a))
    joined_b = " ".join(sorted(words_b))
    return fuzz.token_sort_ratio(joined_a, joined_b)


def match_buyer(acheteur_scrape: str) -> str | None:
    db = SessionLocal()
    known_buyers = db.query(KnownBuyer).all()
    db.close()

    if not known_buyers:
        return None

    candidates = []
    for kb in known_buyers:
        candidates.append((kb.nom_acheteur, kb))
        if kb.variantes:
            for variante in kb.variantes.split(";"):
                candidates.append((variante.strip(), kb))

    target = _normalize(acheteur_scrape)
    if not target:
        return None

    best_score, best_kb = 0, None
    for candidate_name, kb in candidates:
        global_score = fuzz.token_sort_ratio(target, _normalize(candidate_name))
        if global_score < GLOBAL_MATCH_THRESHOLD:
            continue

        # Second contrôle : le mot distinctif doit AUSSI être proche,
        # sinon "Municipalité de Sfax" matcherait "Municipalité de Soukra"
        distinctive_score = _distinctive_similarity(acheteur_scrape, candidate_name)
        if distinctive_score < DISTINCTIVE_WORD_THRESHOLD:
            continue

        if global_score > best_score:
            best_score, best_kb = global_score, kb

    return best_kb.client_sotradies if best_kb else None