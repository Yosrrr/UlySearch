"""Tests du scoring et des garde-fous de l'onboarding.

Les tests d'onboarding simulent le catalogue et Ollama.
Ils ne modifient aucune donnée et ne visitent aucun site.
"""

import json
from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.api import admin_ai_suggest as onboarding
from app.schemas.sotradies import SotradiesRaw
from app.services.keyword_classifier import score_for_category


CATEGORIES = {
    "MATERIEL": {
        "keywords": ["camion"],
    }
}


# Catalogue fictif utilisé uniquement pendant ces tests.
CATALOGUE_TEST = {
    21: {
        "source_id": 21,
        "nom": "BAD",
        "url": (
            "https://www.afdb.org/fr/"
            "projects-and-operations/procurement"
        ),
        "description": "Source internationale de test.",
        "pays": [],
        "international": True,
    },
    23: {
        "source_id": 23,
        "nom": "ONMP",
        "url": "https://www.marchespublics.gov.tn/fr/appels-doffres",
        "description": "Source tunisienne de test.",
        "pays": ["TN"],
        "international": False,
    },
    24: {
        "source_id": 24,
        "nom": "TUNEPS",
        "url": "https://www.tuneps.tn/portail/offres",
        "description": "Source tunisienne de test.",
        "pays": ["TN"],
        "international": False,
    },
}


def _tender(objet: str) -> SotradiesRaw:
    return SotradiesRaw(
        source="test",
        objet=objet,
        acheteur="Acheteur test",
        date_publication=None,
        lien="https://example.invalid/offre",
    )


def _request(**changes) -> onboarding.SuggestRequest:
    data = {
        "description": "Vente de camions en Tunisie.",
        "activite": "Vente de camions en Tunisie.",
        "pays_cibles": ["TN"],
        "veille_internationale": False,
        "langues": ["fr"],
    }
    data.update(changes)
    return onboarding.SuggestRequest(**data)


def _mock_onboarding(
    monkeypatch,
    *,
    selected_ids=(21, 23),
    fail_source_selection=False,
):
    """
    Simule uniquement les services externes.

    generate_suggestion(), ses validations et ses fonctions
    de sélection restent réellement exécutées.
    """
    catalogue_transmis = []

    monkeypatch.setattr(
        onboarding,
        "_load_catalog",
        lambda: deepcopy(CATALOGUE_TEST),
    )

    # Permet aussi de tester la reconnaissance de ONMP/TUNEPS
    # dans le texte sites_connus, indépendamment de la vraie base.
    monkeypatch.setattr(
        onboarding,
        "PUBLIC_ONBOARDING_SOURCES",
        {
            source_id: {"nom": source["nom"]}
            for source_id, source in CATALOGUE_TEST.items()
        },
    )

    def fake_llm(system_prompt, user_prompt, **kwargs):
        schema = kwargs["response_model"]

        if schema is onboarding.ExpandedKeywords:
            return {
                "fr": ["camion", "camions"],
                "ar": [],
                "en": [],
            }

        if schema is onboarding.SourceSelection:
            data = json.loads(user_prompt)

            catalogue_transmis.extend(
                source["source_id"]
                for source in data["catalogue"]
            )

            if fail_source_selection:
                return None

            return {
                "sites": [
                    {
                        "source_id": source_id,
                        "raison": "Suggestion simulée pour ce test.",
                    }
                    for source_id in selected_ids
                ]
            }

        if schema.__name__ == "CategoryPlan":
            return {
                "categories": [
                    {
                        "id": "MATERIEL",
                        "label": "Matériel roulant",
                        "perimetre": "Fourniture de camions.",
                        "preuve": "Vente de camions",
                        "keywords": ["camion"],
                        "marques": [],
                    }
                ]
            }

        raise AssertionError(
            f"Schéma IA non prévu dans le test : {schema}"
        )

    monkeypatch.setattr(
        onboarding,
        "call_local_llm_json",
        fake_llm,
    )

    return catalogue_transmis


# ---------------------------------------------------------------------------
# Tests de scoring existants : conservés
# ---------------------------------------------------------------------------

def test_keyword_match_does_not_match_inside_another_word():
    score, matches = score_for_category(
        _tender("Acquisition de carburant"),
        "MATERIEL",
        CATEGORIES,
        [],
    )

    assert score == 0
    assert matches == []


def test_exact_keyword_match_is_deterministic():
    score, matches = score_for_category(
        _tender("Acquisition de camion"),
        "MATERIEL",
        CATEGORIES,
        [],
    )

    assert score == 60
    assert matches == ["camion"]


# ---------------------------------------------------------------------------
# Garde-fous de la nouvelle version de l'onboarding
# ---------------------------------------------------------------------------

def test_afdb_not_suggested_without_international_scope(monkeypatch):
    """
    L'IA simulée tente de proposer BAD.
    Le backend doit l'ignorer pour une suggestion nationale.
    """
    catalogue_transmis = _mock_onboarding(
        monkeypatch,
        selected_ids=(21, 23),
    )

    result = onboarding.generate_suggestion(_request())

    # BAD ne fait pas partie du catalogue proposé à l'IA.
    assert set(catalogue_transmis) == {23, 24}

    # Même si la réponse IA contient son ID, il n'est pas accepté.
    assert [site.source_id for site in result.sites] == [23]
    assert result.sites[0].nom == "ONMP"
    assert result.sites[0].url == CATALOGUE_TEST[23]["url"]


def test_afdb_can_be_suggested_with_international_scope(monkeypatch):
    """BAD n'est pas bloquée arbitrairement pour tous les clients."""
    _mock_onboarding(monkeypatch, selected_ids=(21, 23))

    result = onboarding.generate_suggestion(
        _request(veille_internationale=True)
    )

    assert {site.source_id for site in result.sites} == {21, 23}


@pytest.mark.parametrize("selection_fails", [False, True])
def test_requested_onmp_tuneps_survive_empty_or_failed_ai(
    monkeypatch,
    selection_fails,
):
    """
    Les choix du client restent présents si l'IA renvoie []
    ou si la sélection complémentaire échoue.
    """
    catalogue_transmis = _mock_onboarding(
        monkeypatch,
        selected_ids=(),
        fail_source_selection=selection_fails,
    )

    result = onboarding.generate_suggestion(
        _request(
            source_ids=[23, 24],
            veille_internationale=True,
        )
    )

    # BAD reste un complément possible, donc la sélection IA
    # est bien appelée dans ce scénario.
    assert set(catalogue_transmis) == {21}

    assert {site.source_id for site in result.sites} == {23, 24}
    assert all(site.origine == "client" for site in result.sites)

    for site in result.sites:
        assert site.url == CATALOGUE_TEST[site.source_id]["url"]


def test_known_sites_text_preserves_onmp_and_tuneps(monkeypatch):
    """
    Compatibilité : les noms dans sites_connus sont reconnus
    lorsque source_ids n'est pas envoyé.
    """
    _mock_onboarding(monkeypatch, selected_ids=())

    result = onboarding.generate_suggestion(
        _request(
            sites_connus="Nous consultons TUNEPS et l'ONMP.",
        )
    )

    assert {site.source_id for site in result.sites} == {23, 24}
    assert all(site.origine == "client" for site in result.sites)


def test_unavailable_requested_source_is_not_silently_removed(monkeypatch):
    _mock_onboarding(monkeypatch)

    with pytest.raises(HTTPException) as error:
        onboarding.generate_suggestion(
            _request(source_ids=[9999])
        )

    assert error.value.status_code == 422