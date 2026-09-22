"""
Récupération du texte brut de la page de détail d'un marché.

Objectif :
- obtenir un texte propre à sauvegarder avant traitement IA ;
- utiliser Playwright pour les pages dynamiques ONMP ;

Important :
- TUNEPS : l'API publique de listing fournit déjà objet, acheteur, référence et dates.
  Pour éviter un fetch Angular lent et fragile, on retourne "" volontairement.
  La description est générée ensuite par l'IA/fallback à partir des métadonnées
  écrites dans raw_dump.py.
"""

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.core.config import settings


PAYWALL_MARKERS = [
    "abonnez-vous pour accéder",
    "connectez-vous ou abonnez-vous",
    "accès complet réservé aux abonnés",
    "réservé aux abonnés",
    "vous devez être connecté",
]



def _is_paywalled(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    return _normalize_text(soup.get_text(" ", strip=True))


def _fetch_static_text(lien: str, timeout: int = 20) -> str:
    """Lecture simple via requests pour les pages non dynamiques."""
    resp = requests.get(
        lien,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    resp.raise_for_status()
    return _extract_text_from_html(resp.text)


def _fetch_dynamic_body_text(lien: str, timeout_ms: int = 30_000) -> str:
    """Lecture d'une page dynamique avec Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(lien, wait_until="networkidle", timeout=timeout_ms)
            return _normalize_text(page.inner_text("body"))
        finally:
            browser.close()


def fetch_onmp_detail_text(lien: str) -> str:
    """ONMP : page dynamique, lecture via Playwright."""
    try:
        return _fetch_dynamic_body_text(lien)
    except Exception as exc:
        print(f"[detail_fetcher] Échec récupération ONMP ({lien}) : {exc}")
        return ""


def _find_first_selector(page, selectors: list[str], timeout_ms: int = 5_000):
    """Retourne le premier sélecteur visible trouvé."""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return None




def fetch_tuneps_detail_text(lien: str) -> str:
    """
    TUNEPS : pas de fetch détail en phase actuelle.

    L'API publique TUNEPS donne déjà :
    - objet ;
    - acheteur ;
    - référence ;
    - date publication ;
    - date limite.

    Ces métadonnées sont écrites dans le dump texte. L'IA/fallback génère
    ensuite une description propre depuis ces champs.
    """
    return ""


def fetch_detail_text(source: str, lien: str) -> str:
    if source == "onmp":
        return fetch_onmp_detail_text(lien)

    
    if source == "tuneps":
        return fetch_tuneps_detail_text(lien)

    return ""