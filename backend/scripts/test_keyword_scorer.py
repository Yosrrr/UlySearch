import pytest

from app.services.keyword_scorer import contains_keyword, first_matching_keyword


@pytest.mark.parametrize("text, keyword, expected", [
    ("Acquisition d'un système d'information", "formation", False),
    ("Travaux de transformation", "formation", False),
    ("FORMATION du personnel", "formation", True),
    ("Formations techniques", "formation", True),
    ("Fourniture de CLIMATISEURS", "climatiseur", True),
    ("Pompes à chaleur", "pompe à chaleur", True),
    ("pompes-a-chaleur réversibles", "pompe à chaleur", True),
    ("Achat de PCB", "PC", False),
    ("Achat de PC portables", "PC", True),
    ("Etude climatique", "clim", False),
])
def test_contains_keyword(text, keyword, expected):
    assert contains_keyword(text, keyword) is expected


def test_first_matching_keyword_ignores_invalid_values():
    assert first_matching_keyword("Système d'information", ["formation", None, "", "information"]) == "information"
    assert first_matching_keyword("Texte", None) is None