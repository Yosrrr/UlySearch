from datetime import datetime

import pytest

from app.schemas.sotradies import SotradiesRaw
from app.services.scrapers.universal_scraper import (
    _parse_date,
    _prepare_page,
    _raw_from_link,
    _same_domain,
)


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-12",
        "12/09/2026",
        "12 septembre 2026",
        "September 12, 2026",
    ],
)
def test_date_formats(value):
    assert _parse_date(value) == datetime(2026, 9, 12)


@pytest.mark.parametrize(
    "url, base_url, expected",
    [
        (
            "https://source.example.test/offres?page=2",
            "https://source.example.test/offres",
            True,
        ),
        (
            "https://source.example.test:443/offres",
            "https://source.example.test/",
            True,
        ),
        (
            "https://compte.example.test/",
            "https://source.example.test/",
            False,
        ),
        (
            "http://source.example.test/",
            "https://source.example.test/",
            False,
        ),
        (
            "https://user:password@source.example.test/",
            "https://source.example.test/",
            False,
        ),
        (
            "/page-suivante",
            "https://source.example.test/",
            False,
        ),
        (
            "",
            "https://source.example.test/",
            False,
        ),
    ],
)
def test_navigation_scope(url, base_url, expected):
    assert _same_domain(url, base_url) is expected


def test_enriched_fields_survive_json_roundtrip():
    expected = {
        "description_detaillee": "Fourniture et installation de climatiseurs.",
        "type_marche": "Fournitures",
        "region_execution": "Tunis",
    }

    # Les champs doivent être déclarés, pas simplement acceptés
    # comme données supplémentaires non typées.
    for field_name in expected:
        assert field_name in SotradiesRaw.model_fields

    raw = SotradiesRaw(
        source="test",
        objet="Fourniture de climatiseurs",
        acheteur="Acheteur de test",
        lien="https://source.example.test/offre/1",
        **expected,
    )

    payload = raw.model_dump(mode="json")
    restored = SotradiesRaw.model_validate(payload)

    for field_name, expected_value in expected.items():
        assert payload[field_name] == expected_value
        assert getattr(restored, field_name) == expected_value


def test_listing_extraction_without_network_or_ai():
    html = """
    <html>
      <body>
        <main>
          <article>
            <a href="/offre/1">Fourniture de climatiseurs pour un bâtiment</a>
            <p>Référence : UNDP-TUN-00123</p>
            <p>Date limite : 12/10/2026</p>
          </article>
          <nav>
            <a href="/offres?page=2">Suivant</a>
          </nav>
        </main>
      </body>
    </html>
    """

    _, _, links = _prepare_page(
        html,
        "https://source.example.test/offres",
    )

    offer_link = next(
        item
        for item in links.values()
        if item["url"] == "https://source.example.test/offre/1"
    )

    assert offer_link["has_ref"] is True
    assert offer_link["has_date"] is True

    raw = _raw_from_link(
        offer_link,
        source_name="web_test",
        default_buyer="Non précisé",
    )

    assert raw is not None
    assert raw.reference == "UNDP-TUN-00123"
    assert raw.date_limite == datetime(2026, 10, 12)
    assert raw.lien == "https://source.example.test/offre/1"

    assert any(
        item["is_next"]
        and item["url"] == "https://source.example.test/offres?page=2"
        for item in links.values()
    )