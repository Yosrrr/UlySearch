from datetime import datetime

from app.schemas.sotradies import SotradiesRaw
from app.services.pipeline import compute_hash


def _tender(source: str) -> SotradiesRaw:
    return SotradiesRaw(
        source=source,
        reference="AO-2026-42",
        objet="Fourniture de camions benne",
        acheteur="Acheteur public test",
        categorie="Fournitures",
        date_publication=datetime(2026, 9, 23, 10, 0),
        lien=f"https://{source}.example/offre",
    )


def test_same_tender_from_two_sources_has_one_identity():
    assert compute_hash(_tender("onmp")) == compute_hash(_tender("tuneps"))
