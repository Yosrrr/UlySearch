from datetime import UTC, date, datetime

import pytest

from app.services.scrapers.undp_dates import extract_undp_dates


def test_dates_et_fuseau_du_listing():
    text = (
        "Title Exemple Ref No UNDP-MRT-00315 "
        "Deadline 05-Oct-26 08:39 AM (New York time) "
        "Posted 22-Sep-26"
    )

    result = extract_undp_dates(text)

    assert result.publication_date == date(2026, 9, 22)
    assert result.deadline_date == date(2026, 10, 5)
    assert result.deadline_utc == datetime(
        2026, 10, 5, 12, 39, tzinfo=UTC
    )


def test_dates_non_etiquetees_non_devinees():
    result = extract_undp_dates(
        "Date quelconque : 22-Sep-26. Autre date : 05-Oct-26."
    )

    assert result.publication_date is None
    assert result.deadline_date is None
    assert result.deadline_utc is None


def test_echeance_sans_heure():
    result = extract_undp_dates(
        "Deadline 05-Oct-2026 Posted 22-Sep-2026"
    )

    assert result.publication_date == date(2026, 9, 22)
    assert result.deadline_date == date(2026, 10, 5)
    assert result.deadline_utc is None


def test_fuseau_absent_non_invente():
    result = extract_undp_dates(
        "Deadline 05-Oct-26 08:39 AM"
    )

    assert result.deadline_date == date(2026, 10, 5)
    assert result.deadline_utc is None


def test_date_invalide_non_acceptee():
    result = extract_undp_dates(
        "Posted 31-Feb-26"
    )

    assert result.publication_date is None


@pytest.mark.parametrize(
    "deadline",
    [
        "01-Nov-26 01:30 AM",  # Heure ambiguë à New York.
        "08-Mar-26 02:30 AM",  # Heure inexistante à New York.
    ],
)
def test_changements_heure_non_devines(deadline):
    result = extract_undp_dates(
        f"Deadline {deadline} (New York time)"
    )

    assert result.deadline_date is not None
    assert result.deadline_utc is None