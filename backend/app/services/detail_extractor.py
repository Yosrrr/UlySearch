"""
Extraction de détails supplémentaires depuis la PAGE DE DÉTAIL de chaque
source — HTML uniquement, pas de PDF/OCR.
"""
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.core.config import settings
from app.services.ai_detail_extractor import clean_and_structure, _EMPTY_RESULT

DEBUG_DIR = Path("debug_detail")
DEBUG_DIR.mkdir(exist_ok=True)

PAYWALL_MARKERS = [
    "abonnez-vous pour accéder",
    "connectez-vous ou abonnez-vous",
]


def _is_paywalled(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)


def extract_onmp_detail(lien: str) -> dict:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(lien, wait_until="networkidle", timeout=30_000)
            full_text = page.inner_text("body")
            browser.close()

        return clean_and_structure(full_text)
    except Exception as e:
        print(f"[detail_extractor] Échec extraction ONMP ({lien}) : {e}")
        return dict(_EMPTY_RESULT)


def extract_appeloffres_detail(lien: str) -> dict:
    if not settings.APPELOFFRES_USERNAME:
        result = dict(_EMPTY_RESULT)
        result["description_detaillee"] = (
            "Contenu complet non accessible — nécessite un abonnement appeloffres.com "
            "(voir le lien source pour les détails)."
        )
        return result

    try:
        resp = requests.get(lien, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        full_text = soup.get_text(" ", strip=True)

        if _is_paywalled(full_text):
            result = dict(_EMPTY_RESULT)
            result["description_detaillee"] = (
                "Contenu complet non accessible — identifiants configurés mais "
                "connexion à appeloffres.com non implémentée pour cette page."
            )
            return result

        return clean_and_structure(full_text)
    except Exception as e:
        print(f"[detail_extractor] Échec extraction appeloffres ({lien}) : {e}")
        return dict(_EMPTY_RESULT)


def extract_detail(source: str, lien: str) -> dict:
    if source == "onmp":
        return extract_onmp_detail(lien)
    elif source == "appeloffres":
        return extract_appeloffres_detail(lien)
    return dict(_EMPTY_RESULT)