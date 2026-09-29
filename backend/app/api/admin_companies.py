"""Sélection sécurisée des entreprises dans l'espace d'administration."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_superadmin
from app.core.database import get_db
from app.models.company import Company

router = APIRouter(prefix="/admin/companies", tags=["admin-companies"])


@router.get("")
def list_companies(
    db: Session = Depends(get_db),
    user=Depends(require_admin_or_superadmin),
):
    query = db.query(Company)
    if user.get("profil") != "superadmin":
        query = query.filter(Company.id == user.get("company_id"))
    return [
        {
            "id": company.id,
            "nom": company.nom,
            "description": (
                company.description_activite
                or company.secteur_activite
                or "Aucune description d'activité renseignée."
            ),
            "secteur": company.secteur_activite,
        }
        for company in query.order_by(Company.nom).all()
    ]