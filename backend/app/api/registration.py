"""
Inscription publique d'un nouveau client — transaction atomique.

Crée en une seule opération :
- User (profil admin)
- Company
- Configuration dédiée (company_id)
- Commercials (company_id)
- CompanySource (ONMP + TUNEPS + sites choisis)
"""
from copy import deepcopy
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.models.commercial import Commercial
from app.models.company import Company
from app.models.company_source import CompanySource
from app.models.configuration import Configuration
from app.models.scraping_source import ScrapingSource
from app.models.user import User

router = APIRouter(prefix="/register", tags=["registration"])


# ── Schémas ──────────────────────────────────────────────

class CommercialInput(BaseModel):
    nom: str
    email: str


class CategoryInput(BaseModel):
    id: str
    label: str
    keywords: list[str]
    marques: list[str] = []
    commercial: str | None = None


class SiteInput(BaseModel):
    nom: str
    url: str
    description: str = ""


class RegisterRequest(BaseModel):
    nom_entreprise: str = Field(..., min_length=2, max_length=255)
    forme_juridique: str | None = None
    matricule_fiscal: str | None = None
    secteur_activite: str | None = None
    annee_creation: int | None = Field(None, ge=1900, le=2030)
    tranche_effectif: str | None = None

    responsable_nom: str | None = None
    responsable_fonction: str | None = None
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    telephone_fixe: str | None = None
    telephone_mobile: str | None = None
    site_web: str | None = None
    linkedin: str | None = None

    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    gouvernorat: str | None = None
    pays: str = "Tunisie"

    description_activite: str | None = None
    produits_services: str | None = None
    marques_representees: list[str] = []
    certifications: list[str] = []
    clients_cibles: str | None = None
    zones_intervention: list[str] = []
    concurrents: str | None = None
    tranche_ca: str | None = None

    types_offres: str | None = None
    budget_min_interet: float | None = Field(None, ge=0)
    budget_max_interet: float | None = Field(None, ge=0)
    sites_consultes: str | None = None
    frequence_alertes: str = "quotidien"

    categories: list[CategoryInput]
    exclusion_keywords: list[str] = []
    sites: list[SiteInput] = []
    commerciaux: list[CommercialInput] = []

    # Rétrocompat
    telephone: str = ""
    region: str = ""


class RegisterResponse(BaseModel):
    message: str
    email: str
    company_id: int
    categories_count: int
    commerciaux_count: int
    sites_count: int


FORMES_JURIDIQUES = [
    "SARL", "SA", "SUARL", "SNC", "SCS",
    "Auto-entrepreneur", "Société civile", "Autre",
]
TRANCHES_EFFECTIF = ["1-10", "11-50", "51-200", "201-500", "500+"]
GOUVERNORATS = [
    "Ariana", "Béja", "Ben Arous", "Bizerte", "Gabès", "Gafsa",
    "Jendouba", "Kairouan", "Kasserine", "Kébili", "Le Kef", "Mahdia",
    "La Manouba", "Médenine", "Monastir", "Nabeul", "Sfax", "Sidi Bouzid",
    "Siliana", "Sousse", "Tataouine", "Tozeur", "Tunis", "Zaghouan",
]
TRANCHES_CA = [
    "< 100 000 TND", "100 000 - 500 000 TND", "500 000 - 1 000 000 TND",
    "1 000 000 - 5 000 000 TND", "5 000 000+ TND",
]
SECTEURS = [
    "BTP / Travaux publics", "Matériel roulant / Transport",
    "Informatique / IT", "Équipements médicaux", "Fournitures de bureau",
    "Agroalimentaire", "Énergie / Électricité", "Télécommunications",
    "Formation / Consulting", "Sécurité / Gardiennage",
    "Nettoyage / Entretien", "Autre",
]

DEDICATED_DEFAULT_SOURCES = [
    {
        "nom": "ONMP",
        "url": "https://www.marchespublics.gov.tn/",
        "type": "dedie",
        "code_hint": "onmp",
    },
    {
        "nom": "TUNEPS",
        "url": "https://www.tuneps.tn/portail/offres",
        "type": "dedie",
        "code_hint": "tuneps",
    },
]


@router.get("/options")
def get_registration_options():
    return {
        "formes_juridiques": FORMES_JURIDIQUES,
        "tranches_effectif": TRANCHES_EFFECTIF,
        "gouvernorats": GOUVERNORATS,
        "tranches_ca": TRANCHES_CA,
        "secteurs": SECTEURS,
        "frequences_alertes": [
            {"value": "instantane", "label": "Instantanée"},
            {"value": "quotidien", "label": "Quotidienne"},
            {"value": "hebdomadaire", "label": "Hebdomadaire"},
        ],
    }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def _get_or_create_source(
    db: Session,
    nom: str,
    url: str,
    source_type: str,
    notes: str = "",
    actif: bool = False,
) -> ScrapingSource:
    """
    Récupère une source existante par URL normalisée approximative,
    sinon la crée. Les sources dédiées restent inactives côté universel
    (le pipeline les gère via OnmpScraper/TunepsScraper).
    """
    url = _normalize_url(url)
    existing = db.query(ScrapingSource).filter_by(url=url).first()
    if existing:
        return existing

    # Fallback : même nom + type dedie
    if source_type == "dedie":
        by_name = (
            db.query(ScrapingSource)
            .filter(ScrapingSource.nom == nom)
            .first()
        )
        if by_name:
            return by_name

    source = ScrapingSource(
        nom=nom.strip()[:255],
        url=url,
        type=source_type,
        actif=actif,
        notes=(notes or "")[:500] if hasattr(ScrapingSource, "notes") else None,
    )
    # notes peut ne pas exister selon le modèle — on reste défensif
    try:
        source.notes = (notes or "")[:500]
    except Exception:
        pass

    db.add(source)
    db.flush()
    return source


def _link_company_source(db: Session, company_id: int, source_id: int) -> None:
    exists = (
        db.query(CompanySource)
        .filter_by(company_id=company_id, source_id=source_id)
        .first()
    )
    if not exists:
        db.add(CompanySource(
            company_id=company_id,
            source_id=source_id,
            actif=True,
        ))


@router.post("", response_model=RegisterResponse)
def register_client(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    email_clean = payload.email.strip().lower()

    if db.query(User).filter_by(email=email_clean).first():
        raise HTTPException(409, "Un compte existe déjà avec cet email.")

    if not payload.categories:
        raise HTTPException(400, "Au moins une catégorie est requise.")

    if payload.matricule_fiscal:
        mf = payload.matricule_fiscal.strip()
        if mf:
            existing_mf = db.query(Company).filter_by(matricule_fiscal=mf).first()
            if existing_mf:
                raise HTTPException(
                    409,
                    "Une entreprise avec ce matricule fiscal existe déjà.",
                )

    # ── Transaction unique ──
    try:
        # 1. User admin (company_id renseigné après création Company)
        user = User(
            email=email_clean,
            nom=(payload.responsable_nom or payload.nom_entreprise).strip()[:255],
            password_hash=hash_password(payload.password),
            profil="admin",
            actif=True,
            company_id=None,
        )
        db.add(user)
        db.flush()

        # 2. Company
        company = Company(
            owner_id=user.id,
            nom=payload.nom_entreprise.strip(),
            forme_juridique=_clean(payload.forme_juridique),
            matricule_fiscal=_clean(payload.matricule_fiscal),
            secteur_activite=_clean(payload.secteur_activite),
            annee_creation=payload.annee_creation,
            tranche_effectif=_clean(payload.tranche_effectif),
            responsable_nom=_clean(payload.responsable_nom),
            responsable_fonction=_clean(payload.responsable_fonction),
            telephone_fixe=_clean(payload.telephone_fixe or payload.telephone),
            telephone_mobile=_clean(payload.telephone_mobile),
            site_web=_clean(payload.site_web),
            linkedin=_clean(payload.linkedin),
            adresse=_clean(payload.adresse),
            code_postal=_clean(payload.code_postal),
            ville=_clean(payload.ville),
            gouvernorat=_clean(payload.gouvernorat or payload.region),
            pays=payload.pays or "Tunisie",
            description_activite=_clean(payload.description_activite),
            produits_services=_clean(payload.produits_services),
            marques_representees=payload.marques_representees or [],
            certifications=payload.certifications or [],
            clients_cibles=_clean(payload.clients_cibles),
            zones_intervention=payload.zones_intervention or [],
            concurrents=_clean(payload.concurrents),
            tranche_ca=_clean(payload.tranche_ca),
            types_offres=_clean(payload.types_offres),
            budget_min_interet=payload.budget_min_interet,
            budget_max_interet=payload.budget_max_interet,
            sites_consultes=_clean(payload.sites_consultes),
            frequence_alertes=payload.frequence_alertes or "quotidien",
            onboarding_complete=True,
        )
        db.add(company)
        db.flush()

        # Lier user → company
        user.company_id = company.id

        # 3. Configuration DÉDIÉE (jamais de fusion globale)
        categories: dict = {}
        rules: dict = {}
        for cat in payload.categories:
            cat_id = cat.id.upper().replace(" ", "_").replace("-", "_")
            if not cat_id:
                continue
            categories[cat_id] = {
                "commercial": cat.commercial,
                "keywords": list(dict.fromkeys(
                    [str(k).strip() for k in (cat.keywords or []) if str(k).strip()]
                )),
                "marques": list(dict.fromkeys(
                    [str(m).strip() for m in (cat.marques or []) if str(m).strip()]
                )),
            }
            if cat.commercial:
                rules[cat_id] = [cat.commercial]

        exclusions = list(dict.fromkeys(
            [str(k).strip() for k in (payload.exclusion_keywords or []) if str(k).strip()]
        ))

        config = Configuration(
            company_id=company.id,
            score_decision_threshold=50,
            score_instant_alert_threshold=70,
            categories=categories,
            exclusion_keywords=exclusions,
            active_sources={
                "onmp": {"actif": True, "frequence": "daily"},
                "tuneps": {"actif": True, "frequence": "daily"},
            },
            assignment_rules=rules,
        )
        db.add(config)

        # 4. Commerciaux (scopés au client)
        created_commercials = 0
        seen_emails: set[str] = set()
        for c in payload.commerciaux:
            nom = c.nom.strip()
            c_email = c.email.strip().lower()
            if not nom or not c_email or c_email in seen_emails:
                continue
            seen_emails.add(c_email)

            existing = (
                db.query(Commercial)
                .filter_by(company_id=company.id, email=c_email)
                .first()
            )
            if existing:
                continue

            db.add(Commercial(
                company_id=company.id,
                nom=nom[:255],
                email=c_email[:255],
                actif=True,
            ))
            created_commercials += 1

        # 5. Sources : ONMP + TUNEPS (dédiées) + sites universels
        sites_count = 0

        for spec in DEDICATED_DEFAULT_SOURCES:
            source = _get_or_create_source(
                db,
                nom=spec["nom"],
                url=spec["url"],
                source_type="dedie",
                notes="Source dédiée (scraper natif)",
                actif=False,  # ne pas passer par UniversalScraper
            )
            _link_company_source(db, company.id, source.id)

        for site in payload.sites:
            url = _normalize_url(site.url)
            if not url:
                continue
            # Sécurité basique SSRF
            host = (urlparse(url).hostname or "").lower()
            if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.endswith(".local"):
                continue

            source = _get_or_create_source(
                db,
                nom=site.nom.strip() or host,
                url=url,
                source_type="universel",
                notes=site.description or "",
                actif=False,  # activation après test technique
            )
            _link_company_source(db, company.id, source.id)
            sites_count += 1

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Échec de l'inscription : {exc}",
        ) from exc

    return RegisterResponse(
        message=(
            f"Compte créé pour {payload.nom_entreprise}. "
            "Vous pouvez maintenant vous connecter."
        ),
        email=email_clean,
        company_id=company.id,
        categories_count=len(categories),
        commerciaux_count=created_commercials,
        sites_count=sites_count,
    )