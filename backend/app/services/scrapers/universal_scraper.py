"""
Scraper universel sécurisé — extraction en deux étapes.

1. Python extrait le texte et le catalogue des liens RÉELS de la page
   (identifiants L1, L2, ...), avec pour chaque lien son contexte HTML.
2. L'IA locale choisit uniquement les identifiants qui correspondent à
   des opportunités ouvertes. Elle ne rédige rien.
3. Python construit chaque offre de façon déterministe à partir du texte
   et du contexte réel du lien : titre, référence, dates.
4. Filet de sécurité déterministe : un lien dont le contexte contient une
   référence ET une date est accepté même si l'IA n'a rien répondu.

L'IA ne peut jamais inventer une URL, une date ou un titre.

Interface identique à OnmpScraper / TunepsScraper :
    UniversalScraper(source_name, url, use_browser, max_pages).fetch_tenders()
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from unidecode import unidecode

from app.schemas.sotradies import SotradiesRaw
from app.services.local_llm_client import call_local_llm_json

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# RÉCUPÉRATION HTML
# ────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8,ar;q=0.7",
}


def _fetch_simple(url: str, timeout: int = 30) -> Optional[str]:
    """HTTP GET classique (rapide, sans JavaScript)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, verify=False) as client:
            resp = client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                logger.warning(f"Contenu non-HTML pour {url}: {content_type}")
                return None
            return resp.text
    except httpx.TimeoutException:
        logger.error(f"Timeout {url}")
    except httpx.HTTPStatusError as exc:
        logger.error(f"HTTP {exc.response.status_code} pour {url}")
    except Exception as exc:
        logger.error(f"Erreur fetch {url}: {exc}")
    return None


def _fetch_browser(url: str, timeout: int = 45) -> Optional[str]:
    """Navigateur réel (Playwright) : attend le DOM puis le contenu principal."""
    try:
        from playwright.sync_api import TimeoutError as PwTimeout, sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = browser.new_context(user_agent=_HEADERS["User-Agent"], locale="fr-FR")
            page = context.new_page()
            page.set_default_navigation_timeout(timeout * 1000)
            try:
                page.goto(url, wait_until="domcontentloaded")
                try:
                    page.locator("main, [role='main'], article, body").first.wait_for(
                        state="attached", timeout=15_000
                    )
                except PwTimeout:
                    logger.warning(f"Contenu principal non détecté pour {url}")
                return page.content()
            finally:
                context.close()
                browser.close()
    except ImportError:
        logger.error("Playwright non installé")
    except Exception as exc:
        logger.error(f"Erreur Playwright {url}: {exc}")
    return None


def _needs_js(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.body.get_text(strip=True) if soup.body else ""
    if len(body_text) < 100:
        return True
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in ("window.__next_data__", "window.__nuxt__", 'id="__next"', 'id="app"', "ng-app")
    )


def _fetch_page(url: str, use_browser: bool = False) -> Optional[str]:
    if use_browser:
        return _fetch_browser(url) or _fetch_simple(url)
    html = _fetch_simple(url)
    if html and _needs_js(html):
        logger.info(f"{url} nécessite JavaScript → Playwright")
        return _fetch_browser(url) or html
    return html


# ────────────────────────────────────────────────────────────────
# NORMALISATION ET MOTIFS
# ────────────────────────────────────────────────────────────────

_NOISE_TAGS = ["script", "style", "nav", "footer", "noscript", "iframe", "svg", "form", "meta", "link", "img"]
_NOISE_CLASSES = re.compile(r"cookie|popup|modal|advert|social|share", re.IGNORECASE)

_MAX_LINKS = 45
_CONTEXT_MIN = 60
_CONTEXT_MAX = 900
_CONTEXT_LEVELS = 6
_CATALOG_TEXT_CHARS = 90
_CATALOG_CONTEXT_CHARS = 160

_MONTHS = r"jan|feb|f[ée]v|mar|apr|avr|may|mai|jun|juin|jul|juil|aug|ao[uû]|sep|sept|oct|nov|dec|d[ée]c"

_DATE_PATTERN = (
    r"(?:\b\d{1,2}[-/ .](?:\d{1,2}|(?:" + _MONTHS + r")[a-zéû]*)[-/ .]\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:" + _MONTHS + r")[a-zéû]*\s+\d{1,2},?\s+\d{4}\b)"
)
_DATE_RE = re.compile(_DATE_PATTERN, re.IGNORECASE)
_DEADLINE_RE = re.compile(
    r"(?:deadline|date limite|closing|cl[ôo]ture|dernier d[ée]lai|expir|آخر أجل)[^0-9]{0,40}?("
    + _DATE_PATTERN + r")",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"\b(?:ADB|AFDB|UNDP|RFP|RFQ|RFI|EOI|ITB|AOO|AON|AOI|AO|N[°º]|R[ée]f\.?)"
    r"[\s:/-]*[A-Z0-9][A-Z0-9/\-\._]{3,40}\b",
    re.IGNORECASE,
)

_EXCLUDED_NOTICE_TERMS = (
    "contract award", "award notice", "attribution de marche", "attribution du marche",
    "avis d'attribution", "resultat d'appel", "resultats d'appel", "marche attribue",
)
_NAV_TEXTS = {
    "home", "accueil", "skip to main content", "aller au contenu", "login", "connexion",
    "contact", "privacy", "cookies", "sitemap", "plan du site",
}
_NEXT_TEXTS = {"next", "next ›", "next »", "›", "»", ">", "suivant", "suivante", "page suivante", "التالي"}


def _compact(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value) -> str:
    return unidecode(_compact(value)).lower()


def _parse_date(text: str) -> Optional[datetime]:
    try:
        parsed = date_parser.parse(text, dayfirst=True, fuzzy=False)
    except Exception:
        return None
    if not 2000 <= parsed.year <= 2100:
        return None
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_open_opportunity(title: str) -> bool:
    normalized = _norm(title)
    return not any(term in normalized for term in _EXCLUDED_NOTICE_TERMS)


# ────────────────────────────────────────────────────────────────
# PRÉPARATION DE LA PAGE : TEXTE + CATALOGUE DE LIENS RÉELS
# ────────────────────────────────────────────────────────────────

def _link_context(anchor) -> str:
    """
    Remonte les parents du lien jusqu'à trouver un bloc qui contient une
    référence ou une date (la "ligne" de l'offre), sans absorber la page.
    """
    best = ""
    node = anchor
    for _ in range(_CONTEXT_LEVELS):
        node = node.parent
        if node is None or node.name in ("body", "html", "[document]"):
            break
        text = _compact(node.get_text(" ", strip=True))
        if len(text) > _CONTEXT_MAX:
            break
        best = text
        if len(text) >= _CONTEXT_MIN and (_DATE_RE.search(text) or _REFERENCE_RE.search(text)):
            break
    return best


def _prepare_page(html: str, base_url: str) -> tuple[str, str, dict[str, dict]]:
    """Retourne (texte de page, catalogue lisible pour l'IA, {lien_id: données})."""
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in _NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    for element in soup.find_all(["div", "section", "aside"], class_=_NOISE_CLASSES):
        element.decompose()

    candidates = []
    seen_urls: set[str] = set()

    for order, anchor in enumerate(soup.find_all("a", href=True)):
        href = _compact(anchor.get("href"))
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        url = urldefrag(urljoin(base_url, href))[0]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or url in seen_urls:
            continue
        seen_urls.add(url)

        text = _compact(anchor.get_text(" ", strip=True))
        if _norm(text) in _NAV_TEXTS:
            continue

        context = _link_context(anchor)
        if len(text) < 2 and len(context) < 10:
            continue

        has_ref = bool(
    _extract_reference(context)
    or _extract_reference(text)
)
        has_date = bool(_DATE_RE.search(context))
        is_next = _norm(text) in _NEXT_TEXTS

        score = 0
        score += 6 if has_ref else 0
        score += 6 if has_date else 0
        score += 5 if is_next else 0
        score += 2 if len(text) >= 25 else 0
        score -= 5 if any(k in _norm(url) for k in ("facebook", "twitter", "linkedin", "youtube", "instagram")) else 0

        candidates.append({
            "url": url, "text": text, "context": context, "order": order,
            "has_ref": has_ref, "has_date": has_date, "is_next": is_next, "score": score,
        })

    candidates.sort(key=lambda c: (-c["score"], c["order"]))
    candidates = candidates[:_MAX_LINKS]

    links_by_id: dict[str, dict] = {}
    catalog_lines = []
    for index, cand in enumerate(candidates, start=1):
        link_id = f"L{index}"
        links_by_id[link_id] = cand
        flags = ("[REF]" if cand["has_ref"] else "") + ("[DATE]" if cand["has_date"] else "") + ("[NEXT]" if cand["is_next"] else "")
        catalog_lines.append(
            f"{link_id} | {flags} {cand['text'][:_CATALOG_TEXT_CHARS]} | "
            f"ctx: {cand['context'][:_CATALOG_CONTEXT_CHARS]}"
        )

    root = soup.find("main") or soup.body or soup
    page_text = _compact(root.get_text("\n", strip=True))[:6000]

    return page_text, "\n".join(catalog_lines), links_by_id


# ────────────────────────────────────────────────────────────────
# ÉTAPE IA : SÉLECTION D'IDENTIFIANTS UNIQUEMENT
# ────────────────────────────────────────────────────────────────

_SYSTEM = (
    "Tu classes des liens extraits d'une page de marchés publics. "
    "Tu réponds UNIQUEMENT en JSON valide, sans commentaire."
)

_SELECT_PROMPT = """Page : {url}

Liste des liens (ID | indicateurs | texte du lien | ctx: contexte autour du lien).
[REF] = une référence de marché a été détectée, [DATE] = une date a été détectée,
[NEXT] = probable lien vers la page suivante.

{link_catalog}

Retourne les ID des liens qui sont des OPPORTUNITÉS ENCORE OUVERTES :
appel d'offres, consultation, RFP, RFQ, EOI, ITB, manifestation d'intérêt,
demande de cotation, avis de sollicitation.

À EXCLURE : Contract Awards, attributions, résultats, archives, navigation,
documents généraux, actualités, offres d'emploi, réseaux sociaux.

Si un lien mène à la page suivante de la liste, mets son ID dans "page_suivante_id".

Réponds strictement :
{{"opportunites": ["L8", "L9"], "page_suivante_id": null}}"""


def _select_opportunity_links(link_catalog: str, url: str) -> tuple[list[str], Optional[str]]:
    result = call_local_llm_json(_SYSTEM, _SELECT_PROMPT.format(url=url, link_catalog=link_catalog))
    if not isinstance(result, dict):
        logger.error(f"Réponse IA invalide pour {url}")
        return [], None
    ids = result.get("opportunites") or result.get("offres") or []
    if not isinstance(ids, list):
        ids = []
    next_id = result.get("page_suivante_id")
    return [str(i).strip() for i in ids if i], (str(next_id).strip() if next_id else None)


# ────────────────────────────────────────────────────────────────
# ÉTAPE DÉTERMINISTE : CONSTRUCTION DE L'OFFRE
# ────────────────────────────────────────────────────────────────

def _extract_dates(context: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Retourne (date_publication, date_limite) à partir du contexte réel du lien."""
    deadline = None
    match = _DEADLINE_RE.search(context)
    if match:
        deadline = _parse_date(match.group(1))

    all_dates = []
    for m in _DATE_RE.finditer(context):
        parsed = _parse_date(m.group(0))
        if parsed:
            all_dates.append(parsed)

    others = [d for d in all_dates if d != deadline]
    publication = None

    if deadline is not None:
        publication = min(others) if others else None
    elif len(all_dates) >= 2:
        publication, deadline = min(all_dates), max(all_dates)
    elif len(all_dates) == 1:
        # Une seule date sans mot-clé : passée → publication ; future → date limite.
        if all_dates[0] <= datetime.now():
            publication = all_dates[0]
        else:
            deadline = all_dates[0]

    return publication, deadline


def _raw_from_link(link_data: dict, source_name: str, default_buyer: str) -> Optional[SotradiesRaw]:
    title = _compact(link_data["text"])
    context = _compact(link_data["context"])

    if len(title) < 15 and len(context) >= 15:
        title = context[:200]
    if len(title) < 10:
        return None
    if not _is_open_opportunity(title) or not _is_open_opportunity(context[:120]):
        logger.info(f"Publication non ouverte rejetée : {title[:80]}")
        return None

    reference = (
    _extract_reference(context)
    or _extract_reference(title)
)
    publication, deadline = _extract_dates(context)

    return SotradiesRaw(
        source=source_name,
        reference=reference,
        objet=title,
        acheteur=default_buyer,
        categorie=None,
        date_publication=publication,
        date_limite=deadline,
        budget_estime=None,
        lien=link_data["url"],
    )


# ────────────────────────────────────────────────────────────────
# CLASSE PRINCIPALE
# ────────────────────────────────────────────────────────────────
_REFERENCE_PATTERNS = (
    re.compile(
        r"\b(?:ADB|AFDB)"
        r"(?:/[A-Z0-9][A-Z0-9._-]*){2,8}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bUNDP-[A-Z]{2,8}-\d{3,10}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:RFP|RFQ|RFI|EOI|ITB|AOO|AON|AOI)"
        r"[-/][A-Z0-9][A-Z0-9/._-]{3,50}\b",
        re.IGNORECASE,
    ),
)


def _extract_reference(text: str) -> str | None:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text or "")

        if match:
            return _compact(match.group(0))

    return None
class UniversalScraper:
    def __init__(
        self,
        source_name: str,
        url: str,
        use_browser: bool = False,
        max_pages: int = 3,
        default_buyer: str = "Non précisé",
    ):
        self.source_name = source_name
        self.url = url
        self.use_browser = use_browser
        self.max_pages = max(1, min(int(max_pages or 1), 10))
        self.default_buyer = default_buyer

    def fetch_tenders(self) -> list[SotradiesRaw]:
        all_tenders: list[SotradiesRaw] = []
        current_url = self.url
        visited: set[str] = set()
        seen_keys: set[str] = set()
        page_num = 0

        while current_url and page_num < self.max_pages:
            if current_url in visited:
                break
            visited.add(current_url)
            page_num += 1
            print(f"[universal] {self.source_name} — page {page_num}/{self.max_pages}: {current_url}")

            html = _fetch_page(current_url, use_browser=self.use_browser)
            if not html:
                print(f"[universal] {self.source_name} — échec fetch")
                break

            page_text, link_catalog, links_by_id = _prepare_page(html, current_url)
            if len(page_text) < 50 or not links_by_id:
                print(f"[universal] {self.source_name} — page vide ou sans lien exploitable")
                break
            print(f"[universal] {self.source_name} — texte : {len(page_text)} chars — liens : {len(links_by_id)}")

            # Étape IA : sélection d'identifiants
            ia_ids, next_id = _select_opportunity_links(link_catalog, current_url)
            print(f"[universal] {self.source_name} — {len(ia_ids)} lien(s) sélectionné(s) par l'IA")

            # Filet déterministe : référence + date dans le contexte réel
            deterministic_ids = [lid for lid, d in links_by_id.items() if d["has_ref"] and d["has_date"]]
            selected = list(dict.fromkeys(ia_ids + deterministic_ids))
            if deterministic_ids:
                print(f"[universal] {self.source_name} — {len(deterministic_ids)} lien(s) avec référence+date (déterministe)")

            accepted = rejected = 0
            for link_id in selected:
                link_data = links_by_id.get(link_id)
                if link_data is None:
                    logger.warning(f"lien_id inventé rejeté : {link_id}")
                    rejected += 1
                    continue
                if link_data["is_next"]:
                    continue
                raw = _raw_from_link(link_data, self.source_name, self.default_buyer)
                if raw is None:
                    rejected += 1
                    continue
                key = (raw.reference or raw.lien.rstrip("/")).lower()
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_tenders.append(raw)
                accepted += 1

            print(f"[universal] {self.source_name} — acceptées={accepted}, rejetées={rejected}")

            # Pagination : IA d'abord, sinon détection déterministe
            next_link = links_by_id.get(next_id) if next_id else None
            if next_link is None:
                next_link = next((d for d in links_by_id.values() if d["is_next"]), None)
            if not next_link or next_link["url"] in visited:
                break
            current_url = next_link["url"]
            time.sleep(3)

        print(f"[universal] {self.source_name} — TOTAL : {len(all_tenders)} offre(s) sur {page_num} page(s)")
        return all_tenders
