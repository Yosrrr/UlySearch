# ============================================================
# app/api/admin_sources.py
# CRUD des sources de scraping + test en direct
# ============================================================

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.api.deps import require_admin_or_superadmin
from app.core.database import session_scope
from app.models.scraping_source import ScrapingSource

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/sources", tags=["admin-sources"])


# ── Schémas ──

class SourceCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=255)
    url: str = Field(..., min_length=10, max_length=1000)
    type: str = Field(default="universel")
    use_browser: bool = False
    max_pages: int = Field(default=3, ge=1, le=10)
    notes: Optional[str] = None


class SourceUpdate(BaseModel):
    nom: Optional[str] = None
    url: Optional[str] = None
    actif: Optional[bool] = None
    use_browser: Optional[bool] = None
    max_pages: Optional[int] = None
    notes: Optional[str] = None


class SourceOut(BaseModel):
    id: int
    nom: str
    url: str
    type: str
    actif: bool
    use_browser: bool
    max_pages: int
    notes: Optional[str] = None
    last_scraped: Optional[str] = None
    last_result_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


# ── Lister ──

@router.get("", response_model=List[SourceOut])
def list_sources(user=Depends(require_admin_or_superadmin)):
    with session_scope() as db:
        sources = (
            db.query(ScrapingSource)
            .order_by(ScrapingSource.created_at.desc())
            .all()
        )
        return [
            SourceOut(
                id=s.id,
                nom=s.nom,
                url=s.url,
                type=s.type,
                actif=s.actif,
                use_browser=s.use_browser or False,
                max_pages=s.max_pages or 3,
                notes=s.notes,
                last_scraped=s.last_scraped.isoformat() if s.last_scraped else None,
                last_result_count=s.last_result_count or 0,
                error_count=s.error_count or 0,
                last_error=s.last_error,
            )
            for s in sources
        ]


# ── Ajouter ──

@router.post("", status_code=201)
def create_source(
    payload: SourceCreate,
    user=Depends(require_admin_or_superadmin),
):
    with session_scope() as db:
        exists = db.query(ScrapingSource).filter_by(url=payload.url).first()
        if exists:
            raise HTTPException(409, f"Cette URL existe déjà : {exists.nom}")

        source = ScrapingSource(
            nom=payload.nom,
            url=payload.url,
            type=payload.type,
            use_browser=payload.use_browser,
            max_pages=payload.max_pages,
            notes=payload.notes,
            actif=True,
        )
        db.add(source)
        db.flush()
        return {"id": source.id, "message": f"Source '{payload.nom}' ajoutée"}


# ── Modifier ──

@router.put("/{source_id}")
def update_source(
    source_id: int,
    payload: SourceUpdate,
    user=Depends(require_admin_or_superadmin),
):
    with session_scope() as db:
        source = db.query(ScrapingSource).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(404, "Source introuvable")

        if payload.nom is not None:
            source.nom = payload.nom
        if payload.url is not None:
            dup = db.query(ScrapingSource).filter(
                ScrapingSource.url == payload.url,
                ScrapingSource.id != source_id,
            ).first()
            if dup:
                raise HTTPException(409, f"URL déjà utilisée par : {dup.nom}")
            source.url = payload.url
        if payload.actif is not None:
            source.actif = payload.actif
        if payload.use_browser is not None:
            source.use_browser = payload.use_browser
        if payload.max_pages is not None:
            source.max_pages = payload.max_pages
        if payload.notes is not None:
            source.notes = payload.notes

        return {"message": f"Source '{source.nom}' mise à jour"}


# ── Supprimer ──

@router.delete("/{source_id}")
def delete_source(
    source_id: int,
    user=Depends(require_admin_or_superadmin),
):
    with session_scope() as db:
        source = db.query(ScrapingSource).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(404, "Source introuvable")
        nom = source.nom
        db.delete(source)
        return {"message": f"Source '{nom}' supprimée"}


# ── Activer / Désactiver ──

@router.patch("/{source_id}/toggle")
def toggle_source(
    source_id: int,
    user=Depends(require_admin_or_superadmin),
):
    with session_scope() as db:
        source = db.query(ScrapingSource).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(404, "Source introuvable")
        source.actif = not source.actif
        status = "activée" if source.actif else "désactivée"
        return {"message": f"Source '{source.nom}' {status}", "actif": source.actif}


# ── TESTER une source (scraping direct, sans sauvegarder) ──

@router.post("/{source_id}/test")
def test_source(
    source_id: int,
    user=Depends(require_admin_or_superadmin),
):
    """
    Lance un scraping de TEST sur une source (1 page max).
    Les offres trouvées sont retournées mais PAS sauvegardées en base.
    """
    with session_scope() as db:
        source = db.query(ScrapingSource).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(404, "Source introuvable")

        from app.services.scrapers.universal_scraper import UniversalScraper

        scraper = UniversalScraper(
            source_name=f"test_{source.id}",
            url=source.url,
            use_browser=source.use_browser or False,
            max_pages=1,
        )

        try:
            tenders = scraper.fetch_tenders()

            source.last_scraped = datetime.utcnow()
            source.last_result_count = len(tenders)
            source.last_error = None

            return {
                "source": source.nom,
                "url": source.url,
                "status": "success",
                "offres_trouvees": len(tenders),
                "apercu": [
                    {
                        "objet": t.objet[:120] if t.objet else None,
                        "acheteur": t.acheteur,
                        "reference": t.reference,
                        "date_publication": (
                            t.date_publication.isoformat()
                            if t.date_publication else None
                        ),
                        "date_limite": (
                            t.date_limite.isoformat()
                            if t.date_limite else None
                        ),
                        "lien": t.lien,
                    }
                    for t in tenders[:10]
                ],
            }
        except Exception as e:
            source.error_count = (source.error_count or 0) + 1
            source.last_error = str(e)[:500]

            return {
                "source": source.nom,
                "url": source.url,
                "status": "error",
                "offres_trouvees": 0,
                "error": str(e),
            }   