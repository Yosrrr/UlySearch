from fastapi import APIRouter, HTTPException, Query
from app.api import schemas

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/sotradies", response_model=list[schemas.SotradieOut])
def list_sotradies(
    search: str | None = Query(default=None),
    marque: str | None = Query(default=None),
    score_min: int | None = Query(default=None),
    statut: str | None = Query(default=None),
):
    items = [
        schemas.SotradieOut(
            id="t-2026-0417",
            reference="AO-2026-0417",
            objet="Acquisition de camions bennes pour la commune de Sfax",
            acheteur="Commune de Sfax",
            source="TUNEPS",
            marque="IVECO",
            categorie="Matériel roulant",
            type_marche="Fournitures",
            score=92,
            is_client_existant=True,
            statut="nouveau",
            date_publication="2026-07-27",
            date_limite="2026-08-20",
            budget="Non communiqué",
            commercial="Ramzi Trabelsi",
        ),
        schemas.SotradieOut(
            id="t-2026-0418",
            reference="AO-2026-0418",
            objet="Fourniture de matériel divers pour travaux de terrassement",
            acheteur="Ministère de l'Équipement",
            source="Observatoire National des Appels d'Offres",
            marque="CASE",
            categorie="Engins TP",
            type_marche="Travaux",
            score=64,
            is_client_existant=False,
            statut="nouveau",
            date_publication="2026-07-28",
            date_limite="2026-08-15",
            budget="Non communiqué",
            commercial="Zied Hajji",
        ),
        schemas.SotradieOut(
            id="t-2026-0419",
            reference="AO-2026-0419",
            objet="Acquisition de chariots élévateurs pour entrepôt logistique",
            acheteur="Office des Ports Nationaux",
            source="Tunisie Appel d'Offre",
            marque="CG Est Manutention",
            categorie="Manutention",
            type_marche="Fournitures",
            score=88,
            is_client_existant=True,
            statut="en_cours",
            date_publication="2026-07-26",
            date_limite="2026-08-05",
            budget="180 000 TND",
            commercial="Salah Gharbi",
        ),
    ]

    if search:
        items = [item for item in items if search.lower() in item.objet.lower()]
    if marque:
        items = [item for item in items if item.marque == marque]
    if score_min is not None:
        items = [item for item in items if item.score >= score_min]
    if statut:
        items = [item for item in items if item.statut == statut]

    return items


@router.get("/sotradies/{sotradie_id}", response_model=schemas.SotradieOut | None)
def get_sotradie(sotradie_id: str):
    item = next((item for item in [
        schemas.SotradieOut(
            id="t-2026-0417",
            reference="AO-2026-0417",
            objet="Acquisition de camions bennes pour la commune de Sfax",
            acheteur="Commune de Sfax",
            source="TUNEPS",
            marque="IVECO",
            categorie="Matériel roulant",
            type_marche="Fournitures",
            score=92,
            is_client_existant=True,
            statut="nouveau",
            date_publication="2026-07-27",
            date_limite="2026-08-20",
            budget="Non communiqué",
            commercial="Ramzi Trabelsi",
        ),
        schemas.SotradieOut(
            id="t-2026-0418",
            reference="AO-2026-0418",
            objet="Fourniture de matériel divers pour travaux de terrassement",
            acheteur="Ministère de l'Équipement",
            source="Observatoire National des Appels d'Offres",
            marque="CASE",
            categorie="Engins TP",
            type_marche="Travaux",
            score=64,
            is_client_existant=False,
            statut="nouveau",
            date_publication="2026-07-28",
            date_limite="2026-08-15",
            budget="Non communiqué",
            commercial="Zied Hajji",
        ),
        schemas.SotradieOut(
            id="t-2026-0419",
            reference="AO-2026-0419",
            objet="Acquisition de chariots élévateurs pour entrepôt logistique",
            acheteur="Office des Ports Nationaux",
            source="Tunisie Appel d'Offre",
            marque="CG Est Manutention",
            categorie="Manutention",
            type_marche="Fournitures",
            score=88,
            is_client_existant=True,
            statut="en_cours",
            date_publication="2026-07-26",
            date_limite="2026-08-05",
            budget="180 000 TND",
            commercial="Salah Gharbi",
        ),
    ] if item.id == sotradie_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Marché introuvable")
    return item
