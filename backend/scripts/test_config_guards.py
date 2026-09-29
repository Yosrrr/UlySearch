import pytest
from fastapi import HTTPException

from app.api.admin_config import _validate_assignment_rules, _validate_categories


COMMERCIALS = {"ully": "ULLY"}


def test_categories_normalize_commercial_name():
    result = _validate_categories(
        {"MATERIEL": {"commercial": "ully", "keywords": ["camion"]}},
        COMMERCIALS,
    )

    assert result["MATERIEL"]["commercial"] == "ULLY"


def test_categories_reject_foreign_commercial():
    with pytest.raises(HTTPException) as error:
        _validate_categories(
            {"MATERIEL": {"commercial": "Ramzi Trabelsi"}},
            COMMERCIALS,
        )

    assert error.value.status_code == 422


def test_assignment_rules_reject_foreign_commercial():
    with pytest.raises(HTTPException):
        _validate_assignment_rules(
            {"MATERIEL": ["Ramzi Trabelsi"]},
            COMMERCIALS,
        )
