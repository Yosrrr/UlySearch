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
import ast
import asyncio
import inspect
import os
from datetime import datetime
from pathlib import Path
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

_DETAIL_SYSTEM = (
    "Tu extrais des informations structurées d'une page d'appel d'offres public. "
    "Tu réponds UNIQUEMENT en JSON valide, sans commentaire. "
    "Si un champ est absent de la page, mets null."
)

_DETAIL_PROMPT = """Voici le texte brut d'une page de détail d'un appel d'offres.
Extrais les informations suivantes et retourne-les en JSON.

Texte de la page :
{page_text}

Retourne exactement ce JSON (null si absent) :
{{
    "reference": "...",
    "objet": "...",
    "acheteur": "...",
    "date_publication": "JJ/MM/AAAA ou null",
    "date_limite": "JJ/MM/AAAA ou null",
    "budget_estime": 0.0,
    "description_detaillee": "...",
    "type_marche": "Fournitures|Travaux|Services|null",
    "procedure_passation": "...",
    "region_execution": "...",
    "lieu_ouverture_offres": "...",
    "caractere_prix": "Ferme|Révisable|null"
}}"""
def _fetch_detail_page(url: str, use_browser: bool = False, auth=None) -> Optional[str]:
    """Récupère le texte brut d'une page de détail d'offre."""
    html = _fetch_page(url, use_browser=use_browser, auth=auth)
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        root = soup.find("main") or soup.body or soup
        text = _compact(root.get_text("\n", strip=True))
        return text[:8000]  # limite pour l'IA
    except Exception as exc:
        logger.warning(f"Erreur extraction texte détail {url}: {exc}")
        return None


def _parse_detail_date(value: str | None) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    return _parse_date(value.strip())


def _enrich_raw_with_detail(
    raw: SotradiesRaw,
    source_name: str,
    use_browser: bool = False,
    auth=None,
) -> SotradiesRaw:
    """
    Va chercher la page de détail d'une offre et enrichit le SotradiesRaw
    avec les champs extraits par l'IA.

    Si la page est inaccessible ou l'IA échoue, retourne le raw original.
    """
    detail_text = _fetch_detail_page(raw.lien, use_browser=use_browser, auth=auth)
    if not detail_text or len(detail_text) < 100:
        logger.warning(f"[{source_name}] Page de détail trop courte ou vide : {raw.lien}")
        return raw

    detail_reference = _extract_reference(detail_text)
    detail_publication, detail_deadline = _extract_dates(detail_text)

    result = call_local_llm_json(
        _DETAIL_SYSTEM,
        _DETAIL_PROMPT.format(page_text=detail_text),
    )

    if not isinstance(result, dict):
        logger.warning(f"[{source_name}] Réponse IA invalide pour détail : {raw.lien}")
        return raw

    # Enrichir seulement les champs absents du raw initial
    def _pick(field: str, current):
        val = result.get(field)
        if val in (None, "", "null", 0, 0.0):
            return current
        return val

    # Dates
    date_pub = _parse_detail_date(result.get("date_publication")) or raw.date_publication
    date_lim = _parse_detail_date(result.get("date_limite")) or raw.date_limite

    # Budget
    try:
        budget = float(result.get("budget_estime") or 0) or raw.budget_estime
    except (TypeError, ValueError):
        budget = raw.budget_estime

    return SotradiesRaw(
        source=raw.source,
        reference=_pick("reference", raw.reference) or detail_reference,
        objet=_pick("objet", raw.objet),
        acheteur=_pick("acheteur", raw.acheteur),
        categorie=raw.categorie,
        date_publication=date_pub or detail_publication,
        date_limite=date_lim or detail_deadline,
        budget_estime=budget,
        lien=raw.lien,
        # Champs enrichis stockés dans extra_fields
        description_detaillee=_pick("description_detaillee", None),
        type_marche=_pick("type_marche", None),
        procedure_passation=_pick("procedure_passation", None),
        region_execution=_pick("region_execution", None),
        lieu_ouverture_offres=_pick("lieu_ouverture_offres", None),
        caractere_prix=_pick("caractere_prix", None),
    )


def _fetch_simple(url: str, timeout: int = 30, auth=None) -> Optional[str]:
    """HTTP GET classique (rapide, sans JavaScript)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, auth=auth) as client:
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


def _fetch_browser(url: str, timeout: int = 45, auth=None) -> Optional[str]:
    """
    Navigateur réel (Playwright) avec stratégie en cascade :
    1. networkidle (sites statiques)
    2. domcontentloaded (SPA, WebSocket, sites avec connexions permanentes)
    """
    try:
        from playwright.sync_api import TimeoutError as PwTimeout, sync_playwright
    except ImportError:
        logger.error("Playwright non installé")
        return None

    browser_loop = None
    previous_loop = None

    try:
        # Uvicorn peut exécuter ce scraper dans un thread équipé d'une
        # boucle Windows Selector, qui ne sait pas lancer le sous-processus
        # Chromium. Playwright a besoin d'une boucle Proactor dédiée.
        if os.name == "nt":
            try:
                previous_loop = asyncio.get_event_loop()
            except RuntimeError:
                previous_loop = None
            browser_loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(browser_loop)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                locale="fr-FR",
                http_credentials=(
                    {"username": auth[0], "password": auth[1]}
                    if auth else None
                ),
            )
            try:
                page = context.new_page()
                nav_timeout = min(timeout, 30) * 1000

                # Tentative 1 : networkidle
                loaded = False
                try:
                    page.goto(url, wait_until="networkidle", timeout=nav_timeout)
                    loaded = True
                except PwTimeout:
                    logger.info(f"{url} : networkidle timeout → domcontentloaded")

                # Tentative 2 : domcontentloaded
                if not loaded:
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
                        loaded = True
                    except PwTimeout:
                        logger.warning(f"{url} : les deux stratégies ont échoué")

                if not loaded:
                    return None

                # Attendre un sélecteur de contenu
                _SELECTORS = [
                    "article", "table tbody tr", "[class*='result']",
                    "[class*='tender']", "[class*='avis']", "[class*='marche']",
                    "li a[href*='detail']", "main", "#content",
                ]
                for selector in _SELECTORS:
                    try:
                        page.locator(selector).first.wait_for(
                            state="attached", timeout=5_000
                        )
                        break
                    except PwTimeout:
                        continue

                # Scroll et pause via Playwright (non bloquant)
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(2_000)

                return page.content()

            finally:
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass

    except Exception as exc:
        logger.error(f"Erreur Playwright {url}: {type(exc).__name__}: {exc}")
        return None
    finally:
        if browser_loop is not None:
            asyncio.set_event_loop(previous_loop)
            browser_loop.close()


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


def _fetch_page(url: str, use_browser: bool = False, auth=None) -> Optional[str]:
    if use_browser:
        return _fetch_browser(url, auth=auth) or _fetch_simple(url, auth=auth)
    html = _fetch_simple(url, auth=auth)
    if html and _needs_js(html):
        logger.info(f"{url} nécessite JavaScript → Playwright")
        return _fetch_browser(url, auth=auth) or html
    return html


# ────────────────────────────────────────────────────────────────
# NORMALISATION ET MOTIFS
# ────────────────────────────────────────────────────────────────
_NOISE_TAGS = ["script", "style", "footer", "noscript", "iframe", "svg", "form", "meta", "link", "img"]
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
# ── Patterns internationaux (existants) ──
_REF_INTERNATIONAL = (
    re.compile(r"\b(?:ADB|AFDB)(?:/[A-Z0-9][A-Z0-9._-]*){2,8}\b", re.IGNORECASE),
    re.compile(r"\bUNDP-[A-Z]{2,8}-\d{3,10}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:RFP|RFQ|RFI|EOI|ITB|AOO|AON|AOI)[-/][A-Z0-9][A-Z0-9/._-]{3,50}\b",
        re.IGNORECASE,
    ),
)

# ── Patterns locaux FR / AR (NOUVEAU — c'était le trou) ──
_REF_LOCAL = (
    re.compile(
        r"\b(?:appels?\s+d['’]offres?|consultation|AO|AON|AOI|AOO|"
        r"march[ée]|N[°ºo]|R[ée]f\.?(?:[ée]rence)?)"
        r"[\s:.\-]*(?:n[°ºo]?[\s:.\-]*)?"
        r"(\d{1,5}\s*/\s*\d{2,4}(?:\s*/\s*[A-Z0-9]{1,10})?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:AO|AON|AOI|AOO|DAO|CPS|MP)[\s]?[-/_][A-Z0-9][A-Z0-9/._-]{3,40}\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:عدد|رقم)\s*[:\-]?\s*(\d{1,5}\s*/\s*\d{2,4})"),
)

_REFERENCE_PATTERNS = _REF_INTERNATIONAL + _REF_LOCAL
_REF_NOISE = re.compile(r"^(?:n[°ºo]|ref\.?|reference)$", re.IGNORECASE)


def _extract_reference(text: str) -> str | None:
    haystack = _compact(text)
    if not haystack:
        return None
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(haystack)
        if not match:
            continue
        value = _compact(match.group(0))
        if len(value) < 4 or _REF_NOISE.match(value):
            continue
        return value
    return None

_EXCLUDED_NOTICE_TERMS = (
    "contract award", "award notice", "attribution de marche", "attribution du marche",
    "avis d'attribution", "resultat d'appel", "resultats d'appel", "marche attribue",
)
_NAV_TEXTS = {
    "home", "accueil", "skip to main content", "aller au contenu", "login", "connexion",
    "contact", "privacy", "cookies", "sitemap", "plan du site",
}
_NEXT_TEXTS_RAW = {
    "next", "next ›", "next »", "›", "»", ">",
    "suivant", "suivante", "page suivante", "التالي",
}
# Normaliser avec unidecode pour que la comparaison fonctionne
_NEXT_TEXTS = {unidecode(t).lower().strip() for t in _NEXT_TEXTS_RAW}

def _compact(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value) -> str:
    return unidecode(_compact(value)).lower()


_FR_MONTHS = {
    "janvier": "january", "février": "february", "fevrier": "february",
    "mars": "march", "avril": "april", "mai": "may", "juin": "june",
    "juillet": "july", "août": "august", "aout": "august",
    "septembre": "september", "octobre": "october",
    "novembre": "november", "décembre": "december", "decembre": "december",
    "janv": "jan", "févr": "feb", "fevr": "feb", "avr": "apr",
    "juil": "jul", "aoû": "aug", "sept": "sep", "déc": "dec",
}
_FR_MONTHS_RE = re.compile(
    r"(?<!\w)(?:"
    + "|".join(
        re.escape(month)
        for month in sorted(_FR_MONTHS, key=len, reverse=True)
    )
    + r")(?!\w)",
    re.IGNORECASE,
)


def _parse_date(text: str) -> Optional[datetime]:
    cleaned = text.strip()
    # Traduire les mois français en anglais pour dateutil
    cleaned = _FR_MONTHS_RE.sub(
        lambda m: _FR_MONTHS.get(m.group(0).lower(), m.group(0)),
        cleaned,
    )
    # Format ISO (AAAA-MM-JJ) : ne pas utiliser dayfirst, sinon 2026-09-12 → 9 décembre
    if re.match(r"\d{4}-\d{2}-\d{2}", cleaned):
        try:
            parsed = datetime.strptime(cleaned[:10], "%Y-%m-%d")
            if 2000 <= parsed.year <= 2100:
                return parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            pass
        return None
    # Autres formats : jour en premier (12/09/2026 = 12 septembre)
    try:
        parsed = date_parser.parse(cleaned, dayfirst=True, fuzzy=False)
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


_FALLBACK_OPPORTUNITY_TERMS = (
    "appel d'offre", "appel d offres", "consultation", "acquisition",
    "fourniture", "travaux", "services", "rfp", "rfq", "eoi", "itb",
    "demande de cotation", "manifestation d'interet", "marche",
)


def _fallback_opportunity_ids(links_by_id: dict[str, dict]) -> list[str]:
    """Sélectionne des liens plausibles lorsque l'IA est indisponible."""
    candidates = []
    for link_id, data in links_by_id.items():
        if data["is_next"]:
            continue
        text = _norm(f'{data["text"]} {data["context"][:240]}')
        has_business_signal = any(term in text for term in _FALLBACK_OPPORTUNITY_TERMS)
        if not (data["has_ref"] or data["has_date"] or has_business_signal):
            continue
        if not _is_open_opportunity(text):
            continue
        candidates.append((data["score"], link_id))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [link_id for _, link_id in candidates[:12]]


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

def _same_domain(url: str, base_url: str) -> bool:
    """
    Autorise uniquement la meme origine :
    protocole, hote et port identiques.

    Ce controle ne constitue pas une protection SSRF complete.
    """
    from urllib.parse import urlsplit

    def origin(value: str) -> tuple[str, str, int]:
        if not isinstance(value, str) or not value:
            raise ValueError("URL absente")

        if "\\" in value or any(
            char.isspace() or ord(char) < 32 or ord(char) == 127
            for char in value
        ):
            raise ValueError("Caracteres interdits dans l'URL")

        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()

        if scheme not in {"http", "https"}:
            raise ValueError("Protocole interdit")

        if not parsed.netloc or not parsed.hostname:
            raise ValueError("URL absolue obligatoire")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Identifiants interdits dans l'URL")

        hostname = (
            parsed.hostname
            .rstrip(".")
            .encode("idna")
            .decode("ascii")
            .lower()
        )

        if not hostname:
            raise ValueError("Hote absent")

        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80

        if not 1 <= port <= 65535:
            raise ValueError("Port invalide")

        return scheme, hostname, port

    try:
        return origin(url) == origin(base_url)
    except (ValueError, TypeError, UnicodeError):
        return False

class UniversalScraper:
    def __init__(
        self,
        source_name: str,
        url: str,
        use_browser: bool = False,
        max_pages: int = 3,
        default_buyer: str = "Non précisé",
        auth=None,
    ):
        self.source_name = source_name
        self.url = url
        self.use_browser = use_browser
        self.max_pages = max(1, min(int(max_pages or 1), 10))
        self.default_buyer = default_buyer
        self.auth = auth

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

            html = _fetch_page(current_url, use_browser=self.use_browser, auth=self.auth)
            if not html:
                print(f"[universal] {self.source_name} — échec fetch")
                if page_num == 1:
                    raise RuntimeError(
                        f"Impossible de charger la première page de {self.source_name} : {current_url}"
                    )
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
            valid_ia_ids = [lid for lid in ia_ids if lid in links_by_id]
            selected = list(dict.fromkeys(valid_ia_ids + deterministic_ids))
            if not selected:
                selected = _fallback_opportunity_ids(links_by_id)
                print(f"[universal] {self.source_name} — fallback déterministe : {len(selected)} lien(s)")
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

                # Enrichissement depuis la page de détail
                try:
                    raw = _enrich_raw_with_detail(
                        raw,
                        source_name=self.source_name,
                        use_browser=self.use_browser,
                        auth=self.auth,
                    )
                    time.sleep(1)  # pause courte entre les requêtes
                except Exception as exc:
                    logger.warning(
                        f"[{self.source_name}] Enrichissement détail échoué "
                        f"({raw.lien}): {exc}"
                    )

                all_tenders.append(raw)
                accepted += 1

            print(f"[universal] {self.source_name} — acceptées={accepted}, rejetées={rejected}")

            # Pagination : IA d'abord, sinon détection déterministe
            next_link = links_by_id.get(next_id) if next_id else None
            if next_link is None:
                next_link = next((d for d in links_by_id.values() if d["is_next"]), None)
            if not next_link or next_link["url"] in visited:
                break
            if not _same_domain(next_link["url"], self.url):
                logger.warning(f"Pagination hors domaine rejetée : {next_link['url']}")
                break
            current_url = next_link["url"]
            time.sleep(3)

        print(f"[universal] {self.source_name} — TOTAL : {len(all_tenders)} offre(s) sur {page_num} page(s)")
        return all_tenders
def main() -> None:
    backend = Path(__file__).resolve().parents[1]
    target = (
        backend
        / "app"
        / "services"
        / "scrapers"
        / "universal_scraper.py"
    )

    if not target.is_file():
        raise SystemExit(f"Fichier introuvable : {target}")

    original = target.read_bytes()
    encoding = (
        "utf-8-sig"
        if original.startswith(b"\xef\xbb\xbf")
        else "utf-8"
    )
    source = original.decode(encoding)
    tree = ast.parse(source, filename=str(target))

    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_same_domain"
    ]

    all_definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_same_domain"
    ]

    if not definitions:
        raise SystemExit(
            "Aucune definition de _same_domain trouvee. "
            "Aucun fichier modifie."
        )

    if (
        len(definitions) != len(all_definitions)
        or any(node.decorator_list for node in definitions)
    ):
        raise SystemExit(
            "Structure inhabituelle : fonction imbriquee ou decoree. "
            "Aucun fichier modifie. Envoyez le code pour verification."
        )

    newline = "\r\n" if b"\r\n" in original else "\n"
    replacement = inspect.getsource(_same_domain).rstrip() + "\n"
    replacement = replacement.replace("\n", newline)

    lines = source.splitlines(keepends=True)

    # Parcours inverse pour conserver les positions des lignes.
    for index in range(len(definitions) - 1, -1, -1):
        node = definitions[index]
        lines[node.lineno - 1:node.end_lineno] = (
            [replacement] if index == 0 else []
        )

    updated = "".join(lines)

    # Controle de syntaxe sans executer le module applicatif.
    compile(updated, str(target), "exec")

    if updated == source:
        print("Le correctif est deja present.")
        print("Fichier :", target)
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = target.with_name(f"{target.name}.{stamp}.bak")

    with backup.open("xb") as handle:
        handle.write(original)

    target.write_bytes(updated.encode(encoding))

    print("Fichier modifie :", target)
    print("Sauvegarde      :", backup)
    print("Definitions remplacees :", len(definitions))
    print("Une seule definition de _same_domain est conservee.")


if __name__ == "__main__":
    main()
