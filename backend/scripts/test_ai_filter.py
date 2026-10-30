"""Phase 3 : extraction factuelle APRÈS rétention. Ne classifie plus : dynamic_categories est ignoré.
Contrat vérifié = ce que pipeline._enrich_with_ai consomme (11 champs + raison d'échec)."""
from app.services import ai_filter_and_extract as m

CHAMPS_PIPELINE = (
    "description_detaillee", "budget_detecte", "duree_execution", "montant_cautionnement",
    "type_marche", "procedure_passation", "region_execution", "date_debut_execution",
    "date_ouverture_offres", "lieu_ouverture_offres", "caractere_prix",
)
REPONSE_LLM = {
    "description": "  Fourniture de  transformateurs   30 kV. ",
    "budget_detecte": 1250000.5, "duree_execution": "6 mois", "montant_cautionnement": None,
    "type_marche": "Fournitures", "procedure_passation": "Appel d'offres ouvert",
    "region_execution": "Kébili", "date_debut_execution": None,
    "date_ouverture_offres": "2026-03-15", "lieu_ouverture_offres": None, "caractere_prix": "Ferme",
}


def _fake_llm(capture: dict):
    def fake(system_prompt, user_prompt, **kwargs):   # accepte response_schema / response_model / num_predict
        capture.update(system_prompt=system_prompt, user_prompt=user_prompt, kwargs=kwargs)
        return dict(REPONSE_LLM)
    return fake


def test_extraction_ne_classifie_plus(monkeypatch):
    capture = {}
    monkeypatch.setattr(m, "call_local_llm_json", _fake_llm(capture))
    categories = {"CAT_TEST": {"marques": ["MARQUE_TEST"], "keywords": ["mot"], "commercial": "Test"}}
    result = m.filter_and_extract("Objet : fourniture de transformateurs", categories)
    assert "CAT_TEST" not in capture["system_prompt"] and "MARQUE_TEST" not in capture["system_prompt"]
    assert not result.get("pertinent") and result.get("categorie") is None   # compatibilité pipeline


def test_extraction_parse_les_champs(monkeypatch):
    monkeypatch.setattr(m, "call_local_llm_json", _fake_llm({}))
    result = m.filter_and_extract("Objet : fourniture de transformateurs", {})
    for champ in CHAMPS_PIPELINE:
        assert champ in result, champ
    assert result["description_detaillee"] == "Fourniture de transformateurs 30 kV."
    assert result["budget_detecte"] == 1250000.5
    assert str(result["date_ouverture_offres"]) == "2026-03-15"
    assert result["type_marche"] == "Fournitures" and result["date_debut_execution"] is None




def test_texte_vide_sans_appel_ia(monkeypatch):
    def interdit(*a, **k):
        raise AssertionError("l'IA ne doit pas être appelée sur un texte vide")
    monkeypatch.setattr(m, "call_local_llm_json", interdit)
    assert m.filter_and_extract("   ", {})["description_detaillee"] is None
