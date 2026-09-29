"""Gestion des sources et abonnements par entreprise."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_superadmin, require_superadmin
from app.core.database import get_db
from app.core.rate_limiter import limiter
from app.models.company import Company
from app.models.company_source import CompanySource
from app.models.scraping_source import ScrapingSource
from app.models.source_account import SourceAccount
from app.services.source_credentials import (
    decrypt_source_password,
    encrypt_source_password,
)
from app.services.source_catalog_service import (
    get_public_source,
    list_public_catalog,
    normalize_source_url,
    propose_source,
    public_profile,
    subscribe_source,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/sources", tags=["admin-sources"])


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str = Field(min_length=2, max_length=255)
    url: str = Field(min_length=3, max_length=1000)
    type: str = "universel"
    use_browser: bool = False
    max_pages: int = Field(default=3, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)
    prive: bool = False
    login: str | None = Field(default=None, min_length=1, max_length=255)
    mot_de_passe: str | None = Field(default=None, min_length=1, max_length=512)


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str | None = Field(default=None, min_length=2, max_length=255)
    url: str | None = Field(default=None, min_length=3, max_length=1000)
    actif: bool | None = None
    use_browser: bool | None = None
    max_pages: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class SourceOut(BaseModel):
    id: int
    nom: str
    url: str
    type: str
    actif: bool
    use_browser: bool
    max_pages: int
    notes: str | None = None
    last_scraped: str | None = None
    last_result_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    abonne: bool = False
    prive: bool = False
    compte_configure: bool = False


def _company_id(user: dict) -> int | None:
    # Un superadmin peut gérer les sources dans le contexte d'une entreprise.
    # Sans contexte explicite, il conserve l'accès au catalogue global.
    if user.get("profil") == "superadmin":
        return user.get("context_company_id")

    company_id = user.get("context_company_id") or user.get("company_id")

    if (
        not isinstance(company_id, int)
        or isinstance(company_id, bool)
        or company_id <= 0
    ):
        raise HTTPException(403, "Compte non rattaché à une entreprise.")

    return company_id


def _visible_source(
    db: Session,
    source_id: int,
    company_id: int | None,
) -> ScrapingSource:
    query = db.query(ScrapingSource)

    if company_id is not None:
        query = query.join(
            CompanySource,
            CompanySource.source_id == ScrapingSource.id,
        ).filter(CompanySource.company_id == company_id)

    source = query.filter(ScrapingSource.id == source_id).one_or_none()

    if source is None:
        raise HTTPException(404, "Source introuvable.")

    return source


def _serialize(source, subscribed: bool, account_configured: bool = False) -> SourceOut:
    profile = public_profile(source, active_required=False)

    return SourceOut(
        id=source.id,
        nom=source.nom,
        url=source.url,
        type=source.type or "universel",
        actif=bool(source.actif),
        use_browser=bool(source.use_browser),
        max_pages=source.max_pages or 3,
        notes=profile["description"] if profile else source.notes,
        last_scraped=(
            source.last_scraped.isoformat()
            if source.last_scraped else None
        ),
        last_result_count=source.last_result_count or 0,
        error_count=source.error_count or 0,
        # Ne pas exposer une exception interne brute aux clients.
        last_error=(
            "Dernier test en erreur ; consulter l'administration."
            if source.last_error else None
        ),
        abonne=subscribed,
        prive=account_configured,
        compte_configure=account_configured,
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflit sur les données de la source.") from exc
    except Exception:
        db.rollback()
        raise


@router.get("/catalog")
def source_catalog(
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    return list_public_catalog(db)


@router.get("", response_model=list[SourceOut])
def list_sources(
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    response.headers["Cache-Control"] = "no-store"
    company_id = _company_id(user)

    if company_id is None:
        sources = db.query(ScrapingSource).order_by(
            ScrapingSource.created_at.desc()
        ).all()

        return [_serialize(source, False) for source in sources]

    rows = (
        db.query(ScrapingSource, CompanySource)
        .join(
            CompanySource,
            CompanySource.source_id == ScrapingSource.id,
        )
        .filter(
            CompanySource.company_id == company_id,
        )
        .order_by(ScrapingSource.created_at.desc())
        .all()
    )

    account_source_ids = {
        account.company_source_id
        for account in db.query(SourceAccount).filter(
            SourceAccount.company_source_id.in_([link.id for _, link in rows])
        ).all()
    } if rows else set()

    return [
        _serialize(source, bool(link.actif), link.id in account_source_ids)
        for source, link in rows
    ]


@router.post("", status_code=201)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    company_id = _company_id(user)

    if payload.type not in ("universel", "dedie"):
        raise HTTPException(422, "Type de source invalide.")
    if payload.prive and (not payload.login or not payload.mot_de_passe):
        raise HTTPException(422, "Le login et le mot de passe sont obligatoires pour un site privé.")
    if payload.prive and company_id is None:
        raise HTTPException(422, "Un site privé doit être rattaché à une entreprise.")
    if not payload.prive and (payload.login or payload.mot_de_passe):
        raise HTTPException(422, "Cochez site privé pour transmettre un compte.")

    try:
        source = propose_source(
            db,
            company_id=company_id,
            nom=payload.nom,
            url=payload.url,
            use_browser=payload.use_browser,
            max_pages=payload.max_pages,
            platform_admin=user.get("profil") == "superadmin",
            activate=True,
        )

        # Les notes privées ne sont pas enregistrées dans
        # les métadonnées d'une source partagée.
        if payload.notes:
            if company_id is None:
                source.notes = payload.notes.strip()
            else:
                company = db.get(Company, company_id)
                if company is None:
                    raise HTTPException(403, "Entreprise introuvable.")

                addition = (
                    f"{source.nom} : {source.url}\n"
                    f"Commentaire : {payload.notes.strip()}"
                )
                company.sites_consultes = "\n\n".join(
                    part
                    for part in (company.sites_consultes, addition)
                    if part
                )

        if payload.prive:
            db.flush()
            link = subscribe_source(db, company_id, source)
            db.flush()
            account = db.query(SourceAccount).filter_by(
                company_source_id=link.id
            ).one_or_none()
            if account is None:
                account = SourceAccount(company_source_id=link.id)
                db.add(account)
            account.login = payload.login.strip()
            account.password_encrypted = encrypt_source_password(payload.mot_de_passe)

        result = {
            "id": source.id,
            "actif": bool(source.actif),
            "message": (
                "Source associée."
                if source.actif
                else "Proposition enregistrée, en attente de validation."
            ),
        }

        _commit(db)
        return result

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflit sur cette source.") from exc
    except Exception:
        db.rollback()
        raise


@router.put("/{source_id}")
def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    source = _visible_source(db, source_id, None)

    if payload.url is not None:
        proposed_url = normalize_source_url(payload.url)
        current_url = normalize_source_url(source.url)

        if proposed_url != current_url:
            raise HTTPException(
                409,
                "Créez une nouvelle proposition au lieu de changer "
                "l'URL d'une source potentiellement partagée.",
            )

    if payload.nom is not None:
        if source.type == "dedie" and payload.nom.strip() != source.nom:
            raise HTTPException(
                422, "Ne renommez pas le connecteur dédié depuis cette route."
            )
        source.nom = payload.nom.strip()

    if payload.actif is True:
        if public_profile(source, active_required=False) is None:
            raise HTTPException(
                409,
                "Approuvez d'abord cette source dans le catalogue "
                "après vérification technique.",
            )
        source.actif = True
    elif payload.actif is False:
        source.actif = False

    if payload.use_browser is not None:
        source.use_browser = payload.use_browser
    if payload.max_pages is not None:
        source.max_pages = payload.max_pages
    if "notes" in payload.model_fields_set:
        source.notes = payload.notes

    _commit(db)
    return {"message": "Source mise à jour."}


@router.delete("/{source_id}")
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    company_id = _company_id(user)
    source = _visible_source(db, source_id, company_id)

    if company_id is None:
        # Préserver les références et historiques.
        source.actif = False
        message = "Source désactivée pour la plateforme."
    else:
        source = db.get(ScrapingSource, source_id)
        if source is None:
            raise HTTPException(404, "Source introuvable.")

        link = (
            db.query(CompanySource)
            .filter_by(company_id=company_id, source_id=source_id)
            .one()
        )
        db.delete(link)
        message = "Source supprimée de votre configuration."

    _commit(db)
    return {"message": message}


@router.patch("/{source_id}/toggle")
def toggle_source(
    source_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    company_id = _company_id(user)

    if company_id is None:
        source = _visible_source(db, source_id, None)

        if not source.actif and public_profile(
            source, active_required=False
        ) is None:
            raise HTTPException(
                409, "Source non approuvée dans le catalogue."
            )

        source.actif = not source.actif
        active = bool(source.actif)

    else:
        source = db.get(ScrapingSource, source_id)
        if source is None:
            raise HTTPException(404, "Source introuvable.")

        link = (
            db.query(CompanySource)
            .filter_by(company_id=company_id, source_id=source_id)
            .one_or_none()
        )

        if link is None:
            source = get_public_source(db, source_id)
            link = subscribe_source(db, company_id, source)
        else:
            link.actif = not link.actif
            if link.actif:
                source.actif = True

        active = bool(link.actif)

    _commit(db)
    return {"actif": active, "message": "Activation mise à jour."}


@router.post("/{source_id}/test")
@limiter.limit("6/hour")
def test_source(
    source_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_superadmin),
):
    """
    Test borné d'une source approuvée.
    Aucun marché inséré et aucune activation automatique.

    Les URL manuelles non approuvées ne sont pas visitées ici.
    """
    company_id = _company_id(user)
    source = _visible_source(db, source_id, company_id)
    profile = public_profile(source, active_required=False)

    if profile is None and source.type != "universel":
        raise HTTPException(
            409,
            "Cette proposition doit être vérifiée et approuvée "
            "avant tout test réseau depuis l'application.",
        )
    if not source.actif:
        raise HTTPException(409, "Activez la source avant de la tester.")

    from app.services.scrapers.onmp_scraper import OnmpScraper
    from app.services.scrapers.tuneps_scraper import TunepsScraper
    from app.services.scrapers.universal_scraper import UniversalScraper

    auth = None
    if company_id is not None:
        link = db.query(CompanySource).filter_by(
            company_id=company_id,
            source_id=source.id,
        ).one_or_none()
        account = db.query(SourceAccount).filter_by(
            company_source_id=link.id,
        ).one_or_none() if link else None
        if account:
            auth = (account.login, decrypt_source_password(account.password_encrypted))

    if source.type == "dedie":
        factories = {
            "onmp": OnmpScraper,
            "tuneps": TunepsScraper,
        }
        factory = factories.get(profile["nom"].strip().lower())
        if factory is None:
            raise HTTPException(422, "Connecteur dédié non disponible.")
        scraper = factory(auth=auth)
    else:
        scraper = UniversalScraper(
            source_name=f"test_{source.id}",
            url=source.url,
            use_browser=bool(source.use_browser),
            max_pages=1,
            auth=auth,
        )

    try:
        tenders = list(scraper.fetch_tenders() or [])
    except Exception:
        logger.exception("Échec de test source id=%s", source_id)
        source.error_count = (source.error_count or 0) + 1
        source.last_error = "Erreur technique pendant le test."
        _commit(db)
        return {
            "status": "error",
            "offres_trouvees": 0,
            "error": "Échec technique. Consulter les logs administrateur.",
        }

    source.last_result_count = len(tenders)

    if tenders:
        source.last_scraped = datetime.now(UTC).replace(tzinfo=None)
        source.last_error = None
    else:
        source.last_error = "Aucune annonce retournée : résultat à examiner."

    result = {
        "status": "success" if tenders else "empty",
        "offres_trouvees": len(tenders),
        "apercu": [
            {
                "objet": tender.objet,
                "acheteur": tender.acheteur,
                "reference": tender.reference,
                "date_publication": (
                    tender.date_publication.isoformat()
                    if tender.date_publication else None
                ),
                "date_limite": (
                    tender.date_limite.isoformat()
                    if tender.date_limite else None
                ),
                "lien": tender.lien,
            }
            for tender in tenders[:5]
        ],
    }

    _commit(db)
    return result