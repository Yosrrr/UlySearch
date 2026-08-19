"""
Récupération du texte brut de la page de détail d'un marché — SANS appel
IA ici. Objectif : obtenir un texte propre à sauvegarder tel quel dans un
fichier .txt (voir raw_dump.py), avant tout traitement par le modèle local.
"""
from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup

from app.core.config import settings

PAYWALL_MARKERS = [
    "abonnez-vous pour accéder",
    "connectez-vous ou abonnez-vous",
]


def _is_paywalled(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)


def fetch_onmp_detail_text(lien: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(lien, wait_until="networkidle", timeout=30_000)
            full_text = page.inner_text("body")
            browser.close()
        return full_text
    except Exception as e:
        print(f"[detail_fetcher] Échec récupération ONMP ({lien}) : {e}")
        return ""


def fetch_appeloffres_detail_text(lien: str) -> str:
    if not settings.APPELOFFRES_USERNAME:
        return "[PAGE NON RÉCUPÉRÉE — abonnement appeloffres.com requis, aucun identifiant configuré]"

    try:
        resp = requests.get(lien, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        full_text = soup.get_text(" ", strip=True)

        if _is_paywalled(full_text):
            return "[PAGE NON RÉCUPÉRÉE — contenu réservé aux abonnés appeloffres.com]"

        return full_text
    except Exception as e:
        print(f"[detail_fetcher] Échec récupération appeloffres ({lien}) : {e}")
        return ""


def fetch_detail_text(source: str, lien: str) -> str:
    if source == "onmp":
        return fetch_onmp_detail_text(lien)
    elif source == "appeloffres":
        return fetch_appeloffres_detail_text(lien)
    return ""