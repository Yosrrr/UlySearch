"""Inscription multi-client et catalogue public de sources."""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limiter import limiter
from app.core.security import hash_password
from app.models.company import Company
from app.models.commercial import Commercial
from app.models.configuration import Configuration
from app.models.user import User
from app.models.company_source import CompanySource
from app.models.source_account import SourceAccount
from app.services.source_catalog_service import (
    get_public_source,
    list_public_catalog,
    normalize_source_url,
    propose_source,
    subscribe_source,
)
from app.services.source_credentials import encrypt_source_password


router = APIRouter(prefix="/register", tags=["registration"])

SourceId = Annotated[int, Field(strict=True, ge=1)]
ShortTerm = Annotated[str, Field(min_length=1, max_length=120)]


class CommercialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str = Field(min_length=2, max_length=255)
    email: EmailStr


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=50)
    label: str = Field(min_length=2, max_length=100)
    keywords: list[ShortTerm] = Field(min_length=1, max_length=100)
    marques: list[ShortTerm] = Field(default_factory=list, max_length=30)
    commercial: str | None = Field(default=None, max_length=255)
    perimetre: str = Field(default="", max_length=400)


class SiteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str = Field(default="", max_length=255)
    url: str = Field(min_length=3, max_length=1000)
    description: str = Field(default="", max_length=2000)
    prive: bool = False
    login: str | None = Field(default=None, min_length=1, max_length=255)
    mot_de_passe: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_private_account(self):
        if self.prive and (not self.login or not self.mot_de_passe):
            raise ValueError(
                "Le login et le mot de passe sont obligatoires pour un site privé."
            )
        if not self.prive and (self.login or self.mot_de_passe):
            raise ValueError(
                "Les identifiants nécessitent l'activation du site privé."
            )
        return self


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom_entreprise: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    forme_juridique: str | None = Field(default=None, max_length=50)
    matricule_fiscal: str | None = Field(default=None, max_length=50)
    secteur_activite: str | None = Field(default=None, max_length=255)
    annee_creation: int | None = Field(default=None, ge=1900, le=2100)
    tranche_effectif: str | None = Field(default=None, max_length=50)

    responsable_nom: str | None = Field(default=None, max_length=255)
    responsable_fonction: str | None = Field(default=None, max_length=255)
    telephone_fixe: str | None = Field(default=None, max_length=20)
    telephone_mobile: str | None = Field(default=None, max_length=20)
    site_web: str | None = Field(default=None, max_length=500)
    linkedin: str | None = Field(default=None, max_length=500)

    adresse: str | None = Field(default=None, max_length=500)
    code_postal: str | None = Field(default=None, max_length=10)
    ville: str | None = Field(default=None, max_length=100)
    gouvernorat: str | None = Field(default=None, max_length=100)
    pays: str = Field(default="Tunisie", min_length=2, max_length=100)

    description_activite: str | None = Field(default=None, max_length=8000)
    produits_services: str | None = Field(default=None, max_length=8000)
    marques_representees: list[ShortTerm] = Field(
        default_factory=list, max_length=30
    )
    certifications: list[ShortTerm] = Field(default_factory=list, max_length=30)
    clients_cibles: str | None = Field(default=None, max_length=4000)
    zones_intervention: list[ShortTerm] = Field(default_factory=list, max_length=50)
    concurrents: str | None = Field(default=None, max_length=4000)
    tranche_ca: str | None = Field(default=None, max_length=50)

    types_offres: str | None = Field(default=None, max_length=4000)
    budget_min_interet: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    budget_max_interet: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    sites_consultes: str | None = Field(default=None, max_length=6000)
    frequence_alertes: Literal[
        "instantane", "quotidien", "hebdomadaire"
    ] = "quotidien"

    categories: list[CategoryInput] = Field(min_length=1, max_length=10)
    exclusion_keywords: list[ShortTerm] = Field(
        default_factory=list, max_length=50
    )
    commerciaux: list[CommercialInput] = Field(
        default_factory=list, max_length=30
    )
    source_ids: list[SourceId] = Field(default_factory=list, max_length=10)
    sites: list[SiteInput] = Field(default_factory=list, max_length=10)

    # Compatibilité avec le formulaire actuel.
    telephone: str = Field(default="", max_length=20)
    region: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def check_budgets(self):
        if (
            self.budget_min_interet is not None
            and self.budget_max_interet is not None
            and self.budget_min_interet > self.budget_max_interet
        ):
            raise ValueError("Le budget minimum dépasse le maximum.")
        return self


class RegisterResponse(BaseModel):
    message: str
    email: str
    company_id: int
    categories_count: int
    commerciaux_count: int
    sites_count: int
    sources_pending_count: int


class PublicSourceOut(BaseModel):
    source_id: int
    nom: str
    url: str
    type: str
    description: str


def _clean(value):
    if value is None:
        return None
    return str(value).strip() or None


def _unique_strings(values):
    result = []
    seen = set()

    for value in values:
        clean = " ".join(value.split())
        key = clean.casefold()

        if clean and key not in seen:
            seen.add(key)
            result.append(clean)

    return result


@router.get("/source-catalog", response_model=list[PublicSourceOut])
def get_source_catalog(
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return list_public_catalog(db)


@router.get("/options")
def get_registration_options():
    return {
        "formes_juridiques": [
            "SARL", "SA", "SUARL", "SNC", "SCS",
            "Auto-entrepreneur", "Société civile", "Autre",
        ],
        "tranches_effectif": ["1-10", "11-50", "51-200", "201-500", "500+"],
        "gouvernorats": [
            "Ariana", "Béja", "Ben Arous", "Bizerte", "Gabès", "Gafsa",
            "Jendouba", "Kairouan", "Kasserine", "Kébili", "Le Kef",
            "Mahdia", "La Manouba", "Médenine", "Monastir", "Nabeul",
            "Sfax", "Sidi Bouzid", "Siliana", "Sousse", "Tataouine",
            "Tozeur", "Tunis", "Zaghouan",
        ],
        "tranches_ca": [
            "< 100 000 TND", "100 000 - 500 000 TND",
            "500 000 - 1 000 000 TND", "1 000 000 - 5 000 000 TND",
            "5 000 000+ TND",
        ],
        "secteurs": [
            "BTP / Travaux publics", "Matériel roulant / Transport",
            "Informatique / IT", "Équipements médicaux",
            "Fournitures de bureau", "Agroalimentaire",
            "Énergie / Électricité", "Télécommunications",
            "Formation / Consulting", "Sécurité / Gardiennage",
            "Nettoyage / Entretien", "Autre",
        ],
        "frequences_alertes": [
            {"value": "instantane", "label": "Instantanée"},
            {"value": "quotidien", "label": "Quotidienne"},
            {"value": "hebdomadaire", "label": "Hebdomadaire"},
        ],
    }


@router.post("", response_model=RegisterResponse, status_code=201)
@limiter.limit("5/hour")
def register_client(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    company_name = _clean(payload.nom_entreprise)

    if not company_name or len(company_name) < 2:
        raise HTTPException(422, "Nom d'entreprise invalide.")

    # Valider les commerciaux sans rechercher ceux d'une autre entreprise.
    commercial_specs = []
    names_seen = set()
    emails_seen = set()

    for item in payload.commerciaux:
        name = item.nom.strip()
        commercial_email = str(item.email).strip().lower()

        if len(name) < 2:
            raise HTTPException(422, "Nom de commercial invalide.")

        if name.casefold() in names_seen or commercial_email in emails_seen:
            raise HTTPException(
                422, "Commercial dupliqué dans le formulaire."
            )

        names_seen.add(name.casefold())
        emails_seen.add(commercial_email)
        commercial_specs.append({
            "nom": name,
            "email": commercial_email,
        })

    commercial_names = {
        item["nom"].casefold(): item["nom"]
        for item in commercial_specs
    }

    categories = {}
    rules = {}

    for category in payload.categories:
        category_id = re.sub(
            r"[\s-]+", "_", category.id.strip().upper()
        )

        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,49}", category_id):
            raise HTTPException(422, "Identifiant de catégorie invalide.")

        if category_id in categories:
            raise HTTPException(422, "Catégorie dupliquée.")

        assigned = _clean(category.commercial)
        if assigned:
            assigned = commercial_names.get(assigned.casefold())
            if assigned is None:
                raise HTTPException(
                    422,
                    "Une catégorie référence un commercial "
                    "absent de cette inscription.",
                )

        keywords = _unique_strings(category.keywords)
        if not keywords:
            raise HTTPException(
                422, f"Aucun mot-clé pour {category_id}."
            )

        categories[category_id] = {
            "label": category.label.strip(),
            "perimetre": category.perimetre.strip(),
            "keywords": keywords,
            "marques": _unique_strings(category.marques),
            "commercial": assigned,
        }

        if assigned:
            rules[category_id] = [assigned]

    manual_specs = [
        {
            "nom": site.nom.strip(),
            "url": normalize_source_url(site.url),
            "description": site.description.strip(),
            "prive": site.prive,
            "login": site.login.strip() if site.login else None,
            "mot_de_passe": site.mot_de_passe,
        }
        for site in payload.sites
    ]

    company_fields = {
        "forme_juridique", "matricule_fiscal", "secteur_activite",
        "annee_creation", "tranche_effectif", "responsable_nom",
        "responsable_fonction", "telephone_mobile", "site_web",
        "linkedin", "adresse", "code_postal", "ville", "pays",
        "description_activite", "produits_services", "marques_representees",
        "certifications", "clients_cibles", "zones_intervention",
        "concurrents", "tranche_ca", "types_offres", "budget_min_interet",
        "budget_max_interet", "sites_consultes", "frequence_alertes",
    }

    company_data = payload.model_dump(include=company_fields)

    for key, value in company_data.items():
        if isinstance(value, str):
            company_data[key] = _clean(value)

    company_data["pays"] = company_data.get("pays") or "Tunisie"
    company_data["marques_representees"] = _unique_strings(
        payload.marques_representees
    )

    # Les commentaires des liens manuels restent dans le profil
    # de cette entreprise, pas dans le catalogue public.
    manual_notes = [
        (
            f"{site['nom'] or 'Site manuel'} : {site['url']}"
            + (
                f"\nCommentaire : {site['description']}"
                if site["description"] else ""
            )
        )
        for site in manual_specs
    ]

    company_data["sites_consultes"] = "\n\n".join(
        part
        for part in [
            _clean(payload.sites_consultes),
            "\n\n".join(manual_notes),
        ]
        if part
    ) or None

    try:
        if (
            db.query(User)
            .filter(func.lower(User.email) == email)
            .first()
        ):
            raise HTTPException(409, "Cet email possède déjà un compte.")

        fiscal_id = company_data.get("matricule_fiscal")
        if fiscal_id and (
            db.query(Company)
            .filter_by(matricule_fiscal=fiscal_id)
            .first()
        ):
            raise HTTPException(409, "Matricule fiscal déjà enregistré.")

        # 1. Entreprise.
        company = Company(
            nom=company_name,
            owner_id=None,
            telephone_fixe=_clean(
                payload.telephone_fixe or payload.telephone
            ),
            gouvernorat=_clean(
                payload.gouvernorat or payload.region
            ),
            onboarding_complete=True,
            **company_data,
        )
        db.add(company)
        db.flush()

        # 2. Compte administrateur de CETTE entreprise.
        user = User(
            email=email,
            nom=_clean(payload.responsable_nom) or company_name,
            password_hash=hash_password(payload.password),
            profil="admin",
            actif=True,
            company_id=company.id,
        )
        db.add(user)
        db.flush()
        company.owner_id = user.id

        # 3. Ses commerciaux.
        for item in commercial_specs:
            db.add(Commercial(
                company_id=company.id,
                nom=item["nom"],
                email=item["email"],
                actif=True,
            ))

        # 4. Ses abonnements.
        selected_sources = {}

        for source_id in dict.fromkeys(payload.source_ids):
            source = get_public_source(db, source_id)
            subscribe_source(db, company.id, source)
            selected_sources[source.id] = source

        for site in manual_specs:
            source = propose_source(
                db,
                company_id=company.id,
                nom=site["nom"],
                url=site["url"],
                activate=True,   # sources validées par le client → actives immédiatement
            )
            if site["prive"]:
                link = db.query(CompanySource).filter_by(
                    company_id=company.id,
                    source_id=source.id,
                ).one()
                db.add(SourceAccount(
                    company_source_id=link.id,
                    login=site["login"],
                    password_encrypted=encrypt_source_password(
                        site["mot_de_passe"]
                    ),
                ))
            selected_sources[source.id] = source

        if len(selected_sources) > 10:
            raise HTTPException(422, "Maximum 10 sources par inscription.")

        active_sources = {
            "onmp": {"actif": False, "frequence": "daily"},
            "tuneps": {"actif": False, "frequence": "daily"},
        }

        for source in selected_sources.values():
            code = source.nom.strip().lower()
            if source.type == "dedie" and code in active_sources:
                active_sources[code]["actif"] = True

        # 5. Sa configuration : aucune fusion globale.
        db.add(Configuration(
            company_id=company.id,
            score_decision_threshold=50,
            score_instant_alert_threshold=70,
            categories=categories,
            exclusion_keywords=_unique_strings(
                payload.exclusion_keywords
            ),
            assignment_rules=rules,
            active_sources=active_sources,
        ))

        pending = sum(
            not bool(source.actif)
            for source in selected_sources.values()
        )

        result = RegisterResponse(
            message=(
                "Compte créé. Les nouvelles sources restent "
                "inactives jusqu'à leur validation."
            ),
            email=email,
            company_id=company.id,
            categories_count=len(categories),
            commerciaux_count=len(commercial_specs),
            sites_count=len(selected_sources),
            sources_pending_count=pending,
        )

        db.commit()
        try:
            from app.workers.tasks import run_pipeline_for_new_client
            run_pipeline_for_new_client.apply_async(
                args=[company.id],
                countdown=30,   # 30 secondes pour laisser le commit se propager
            )
            print(f"[register] Pipeline immédiat planifié pour company_id={company.id}")
        except Exception as exc:
            # Celery peut ne pas être disponible en développement
            print(f"[register] Pipeline immédiat non lancé (Celery indisponible): {exc}")

        response.headers["Cache-Control"] = "no-store"
        return result
    

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "Conflit pendant l'inscription. Vérifiez les informations "
            "ou contactez l'administrateur.",
        ) from exc
    except Exception:
        db.rollback()
        raise