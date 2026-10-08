r"""
Applique directement :
 1. buyers.py : rematch_all_tenders(company_id=...) -> rematch_company_tenders(...)
 2. detail_fetcher.py : version sécurisée complète (F-005)
Sauvegardes : buyers.py.bak6, detail_fetcher.py.bak6
Usage : python scripts\apply_final_fixes.py
"""
import re
from pathlib import Path

B = Path(__file__).resolve().parents[1]

# ---------- 1. buyers.py ----------
p = B / "app" / "api" / "buyers.py"
s = p.read_text(encoding="utf-8-sig")
p.with_suffix(".py.bak6").write_text(s, encoding="utf-8")
s = re.sub(r"rematch_all_tenders\s*,\s*company_id\s*=\s*buyer\.company_id",
           "rematch_company_tenders, buyer.company_id", s)
s = s.replace("rematch_all_tenders", "rematch_company_tenders")
compile(s, str(p), "exec")
p.write_text(s, encoding="utf-8")
print("[1] buyers.py : rematch_all_tenders restants =", s.count("rematch_all_tenders"))

# ---------- 2. detail_fetcher.py ----------
DETAIL = r'''"""
Récupération du texte de la page de détail d'un marché.

- ONMP : page dynamique (Playwright).
- TUNEPS : "" volontairement (l'API publique fournit déjà les métadonnées).
- Sources web_* : HTML de détail + PDF liés.

Sécurité (F-005) :
- chaque requête httpx, redirections comprises, est vérifiée (_ssrf_hook) ;
- Playwright bloque toute requête vers une adresse interne (page.route) ;
- page d'erreur (4xx/5xx), page payante ou adresse bloquée -> "" (jamais envoyé à l'IA).
"""
import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

PAYWALL_MARKERS = [
    "abonnez-vous pour accéder",
    "connectez-vous ou abonnez-vous",
    "accès complet réservé aux abonnés",
    "réservé aux abonnés",
    "vous devez être connecté",
    "connexion à votre espace client",
    "identifiant:",
    "mot de passe",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.7",
}
_MAX_HTML_BYTES = 5_000_000
_MAX_PDF_BYTES = 8_000_000
_MAX_DETAIL_CHARS = 15000


def _is_safe(url: str) -> bool:
    from app.services.scrapers.universal_scraper import _is_safe_url
    return _is_safe_url(url)


def _ssrf_hook(request) -> None:
    """Appelé par httpx avant CHAQUE requête, redirections comprises."""
    from app.services.scrapers.universal_scraper import _check_request
    _check_request(request)


def _client(timeout: int) -> httpx.Client:
    return httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS,
                        event_hooks={"request": [_ssrf_hook]})


def _is_paywalled(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)


def _normalize_text(text: str | None) -> str:
    return " ".join(text.split()) if text else ""


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "nav", "footer", "noscript", "iframe"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return _normalize_text(root.get_text(" ", strip=True))


def _fetch_dynamic_body_text(lien: str, timeout_ms: int = 30_000) -> str:
    """Page dynamique. Toute requête vers une adresse interne est bloquée."""
    if not _is_safe(lien):
        logger.warning("URL bloquée (adresse interne) : %s", lien)
        return ""

    def _guard(route):
        url = route.request.url
        if url.startswith(("http://", "https://")) and not _is_safe(url):
            logger.warning("Requête navigateur bloquée : %s", url)
            return route.abort()
        return route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/*", _guard)
            response = page.goto(lien, wait_until="networkidle", timeout=timeout_ms)
            if response is None or response.status >= 400:
                return ""
            return _normalize_text(page.inner_text("body"))
        finally:
            browser.close()


def _find_first_selector(page, selectors: list[str], timeout_ms: int = 5_000):
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


def fetch_onmp_detail_text(lien: str) -> str:
    try:
        return _fetch_dynamic_body_text(lien)
    except Exception as exc:
        logger.warning("Échec récupération ONMP (%s) : %s", lien, exc)
        return ""


def fetch_tuneps_detail_text(lien: str) -> str:
    """TUNEPS : métadonnées déjà fournies par l'API publique."""
    return ""


def _fetch_html(lien: str, timeout: int = 25) -> str:
    with _client(timeout) as client:
        resp = client.get(lien)
        resp.raise_for_status()
        if len(resp.content) > _MAX_HTML_BYTES:
            logger.warning("HTML trop volumineux : %s", lien)
            return ""
        if "pdf" in (resp.headers.get("content-type") or "").lower():
            return ""
        return resp.text


def _extract_pdf_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"].strip())
        if urlparse(full).path.lower().endswith(".pdf") or "pdf" in (a.get_text() or "").lower():
            if full not in links:
                links.append(full)
    return links[:3]


def _pdf_to_text(url: str, timeout: int = 30) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) non installé")
        return ""
    try:
        with _client(timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            if len(resp.content) > _MAX_PDF_BYTES:
                logger.warning("PDF trop volumineux : %s", url)
                return ""
            data = resp.content
    except Exception as exc:
        logger.warning("Échec téléchargement PDF %s : %s", url, exc)
        return ""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        parts = [page.get_text("text") for i, page in enumerate(doc) if i < 10]
        doc.close()
        return _normalize_text("\n".join(parts))
    except Exception as exc:
        logger.warning("Échec lecture PDF %s : %s", url, exc)
        return ""


def fetch_universal_detail_text(lien: str) -> str:
    if not lien or not str(lien).startswith(("http://", "https://")):
        return ""
    if not _is_safe(lien):
        logger.warning("URL bloquée (adresse interne) : %s", lien)
        return ""

    try:
        html = _fetch_html(lien)
    except httpx.HTTPStatusError as exc:
        logger.warning("Détail inaccessible (HTTP %s) : %s", exc.response.status_code, lien)
        return ""
    except httpx.RequestError as exc:
        if "bloquée" in str(exc):
            logger.warning("Redirection bloquée : %s", lien)
            return ""
        try:
            text = _fetch_dynamic_body_text(lien)[:_MAX_DETAIL_CHARS]
        except Exception:
            return ""
        return "" if not text or _is_paywalled(text) else text

    chunks: list[str] = []
    page_text = _extract_text_from_html(html)
    if page_text and _is_paywalled(page_text):
        logger.info("Page payante détectée : %s", lien)
        return ""
    if page_text:
        chunks.append(page_text)

    for pdf_url in _extract_pdf_links(html, lien):
        pdf_text = _pdf_to_text(pdf_url)
        if pdf_text and not _is_paywalled(pdf_text):
            chunks.append(f"[PDF] {pdf_text}")

    if not chunks and lien.lower().split("?")[0].endswith(".pdf"):
        pdf_text = _pdf_to_text(lien)
        if pdf_text:
            chunks.append(pdf_text)

    return _normalize_text("\n\n".join(chunks))[:_MAX_DETAIL_CHARS]


def fetch_detail_text(source: str, lien: str) -> str:
    source = (source or "").strip().lower()
    if source == "onmp":
        return fetch_onmp_detail_text(lien)
    if source == "tuneps":
        return fetch_tuneps_detail_text(lien)
    if lien and str(lien).startswith(("http://", "https://")):
        return fetch_universal_detail_text(lien)
    return ""
'''

p = B / "app" / "services" / "detail_fetcher.py"
old = p.read_text(encoding="utf-8-sig")
p.with_suffix(".py.bak6").write_text(old, encoding="utf-8")
compile(DETAIL, str(p), "exec")
p.write_text(DETAIL, encoding="utf-8")
print("[2] detail_fetcher.py : _is_safe présent =", "def _is_safe" in p.read_text(encoding="utf-8"))
print("Terminé. Sauvegardes : *.bak6")