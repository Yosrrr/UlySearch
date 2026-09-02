"""
Récupération du texte brut de la page de détail d'un marché.

Objectif :
- obtenir un texte propre à sauvegarder avant traitement IA ;
- utiliser Playwright pour les pages dynamiques ONMP ;
- garder un mode public propre pour appeloffres.com ;
- préparer une authentification appeloffres.com autorisée, dès que le client fournit
  un compte valide.

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

APPELOFFRES_LOGIN_URL = "https://www.appeloffres.com/login"


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


def fetch_appeloffres_detail_text(lien: str) -> str:
    """
    Récupère le détail sur appeloffres.com.

    - Sans identifiants : mode public uniquement.
    - Avec identifiants : tentative d'accès authentifié autorisé.
      Les sélecteurs devront être validés avec le compte réel client.
    """
    username = (settings.APPELOFFRES_USERNAME or "").strip()
    password = settings.APPELOFFRES_PASSWORD or ""

    # Mode public
    if not username or not password:
        print("[detail_fetcher] Mode public appeloffres.com — identifiants absents.")
        try:
            full_text = _fetch_static_text(lien, timeout=15)
            if _is_paywalled(full_text):
                return (
                    "[PAGE NON RÉCUPÉRÉE — contenu réservé aux abonnés "
                    "appeloffres.com]"
                )
            return full_text
        except Exception as exc:
            print(f"[detail_fetcher] Échec public appeloffres ({lien}) : {exc}")
            return ""

    # Mode authentifié — à valider quand le client fournit le compte réel.
    print("[detail_fetcher] Tentative d'accès authentifié appeloffres.com.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(
                    APPELOFFRES_LOGIN_URL,
                    wait_until="networkidle",
                    timeout=30_000,
                )

                email_input = _find_first_selector(
                    page,
                    [
                        "input[type='email']",
                        "input[name='email']",
                        "input[name='username']",
                        "input#email",
                        "input#username",
                    ],
                )

                password_input = _find_first_selector(
                    page,
                    [
                        "input[type='password']",
                        "input[name='password']",
                        "input#password",
                    ],
                )

                if not email_input or not password_input:
                    print("[detail_fetcher] Formulaire login appeloffres introuvable.")
                    return "[PAGE NON RÉCUPÉRÉE — formulaire login introuvable]"

                email_input.fill(username)
                password_input.fill(password)

                submit_button = _find_first_selector(
                    page,
                    [
                        "button[type='submit']",
                        "input[type='submit']",
                        "button:has-text('Connexion')",
                        "button:has-text('Se connecter')",
                        "button:has-text('Login')",
                    ],
                    timeout_ms=3_000,
                )

                if submit_button:
                    submit_button.click()
                else:
                    password_input.press("Enter")

                page.wait_for_timeout(3_000)

                page.goto(lien, wait_until="networkidle", timeout=30_000)
                full_text = _normalize_text(page.inner_text("body"))

                if _is_paywalled(full_text):
                    print(
                        "[detail_fetcher] Page toujours paywallée après login — "
                        "identifiants invalides, abonnement inactif ou sélecteurs à ajuster."
                    )
                    return "[PAGE NON RÉCUPÉRÉE — abonnement inactif ou échec login]"

                print("[detail_fetcher] Détail appeloffres récupéré avec session authentifiée.")
                return full_text

            finally:
                browser.close()

    except Exception as exc:
        print(f"[detail_fetcher] Échec auth appeloffres ({lien}) : {exc}")
        return ""


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

    if source == "appeloffres":
        return fetch_appeloffres_detail_text(lien)

    if source == "tuneps":
        return fetch_tuneps_detail_text(lien)

    return ""