"""Catalogue public et propositions de sources.

Aucune requête réseau dans ce module.
Aucun commit : la transaction appartient à l'appelant.
"""

import ipaddress
import re
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.onboarding_sources import PUBLIC_ONBOARDING_SOURCES
from app.models.company_source import CompanySource
from app.models.scraping_source import ScrapingSource


URL_ADAPTER = TypeAdapter(HttpUrl)


def normalize_source_url(value: str) -> str:
    """Normalisation syntaxique, sans résolution DNS ni téléchargement."""
    value = (value or "").strip()

    if not value:
        raise HTTPException(422, "Le lien du site est obligatoire.")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
        value = "https://" + value

    try:
        normalized = str(URL_ADAPTER.validate_python(value))
        parsed = urlsplit(normalized)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, "URL HTTP/HTTPS invalide.") from exc

    if not hostname:
        raise HTTPException(422, "Le domaine du site est absent.")

    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(
            422,
            "Ne placez aucun identifiant ou mot de passe dans une URL.",
        )

    if port not in (None, 80, 443):
        raise HTTPException(
            422,
            "Seuls les ports HTTP/HTTPS standards sont acceptés.",
        )

    if (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
    ):
        raise HTTPException(422, "Les adresses internes sont interdites.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None and not address.is_global:
        raise HTTPException(422, "Les adresses réseau internes sont interdites.")

    if address is None and "." not in hostname:
        raise HTTPException(422, "Un nom de domaine public est nécessaire.")

    if len(normalized) > 1000:
        raise HTTPException(422, "URL trop longue.")

    # Ne pas supprimer arbitrairement le chemin, les paramètres
    # ou le fragment : ils peuvent être utiles au site.
    return normalized


def public_profile(
    source: ScrapingSource,
    *,
    active_required: bool = True,
) -> dict | None:
    """Vérifie l'appartenance au catalogue explicitement approuvé."""
    profile = PUBLIC_ONBOARDING_SOURCES.get(source.id)

    if profile is None:
        return None

    if active_required and not source.actif:
        return None

    if source.type != profile["type"]:
        return None

    try:
        url = normalize_source_url(source.url)
        hostname = (urlsplit(url).hostname or "").lower()
    except HTTPException:
        return None

    allowed_hosts = {
        str(host).lower()
        for host in profile["hosts"]
    }

    if hostname not in allowed_hosts:
        return None

    return profile


def list_public_catalog(db: Session) -> list[dict]:
    """Retourne uniquement les sources approuvées et actives."""
    ids = list(PUBLIC_ONBOARDING_SOURCES)

    if not ids:
        return []

    sources = (
        db.query(ScrapingSource)
        .filter(ScrapingSource.id.in_(ids))
        .order_by(ScrapingSource.id.asc())
        .all()
    )

    result = []

    for source in sources:
        profile = public_profile(source)

        if profile is None:
            continue

        result.append({
            "source_id": source.id,
            "nom": profile["nom"],
            "url": source.url,
            "type": source.type,
            "description": profile["description"],
        })

    return result


def get_public_source(db: Session, source_id: int) -> ScrapingSource:
    source = db.get(ScrapingSource, source_id)

    if source is None or public_profile(source) is None:
        raise HTTPException(
            422,
            "Une source sélectionnée est absente ou indisponible "
            "dans le catalogue public.",
        )

    return source


def subscribe_source(
    db: Session,
    company_id: int,
    source: ScrapingSource,
) -> CompanySource:
    """Crée ou réactive uniquement l'abonnement de cette entreprise."""
    if company_id is None or company_id <= 0:
        raise ValueError("company_id obligatoire.")

    link = (
        db.query(CompanySource)
        .filter_by(company_id=company_id, source_id=source.id)
        .one_or_none()
    )

    if link is None:
        link = CompanySource(
            company_id=company_id,
            source_id=source.id,
            actif=True,
        )
        db.add(link)
    else:
        link.actif = True

    return link


def propose_source(
    db,
    *,
    company_id: int | None,
    nom: str,
    url: str,
    use_browser: bool = False,
    max_pages: int = 3,
    platform_admin: bool = False,
    activate: bool = False,
) -> ScrapingSource:
    if company_id is None and not platform_admin:
        raise ValueError("company_id obligatoire pour proposer une source.")

    normalized = normalize_source_url(url)

    existing = (
        db.query(ScrapingSource)
        .filter(ScrapingSource.url == normalized)
        .first()
    )

    if existing is None:
        existing = ScrapingSource(
            nom=nom or normalized,
            type="universel",
            url=normalized,
            actif=activate,
            use_browser=use_browser,
            max_pages=max_pages,
        )
        db.add(existing)
        db.flush()
    elif activate and not existing.actif:
        existing.actif = True

    if company_id is not None:
        subscribe_source(db, company_id, existing)
    return existing
