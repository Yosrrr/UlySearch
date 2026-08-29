from app.services import ai_filter_and_extract


def test_filter_and_extract_uses_dynamic_categories(monkeypatch):
    captured = {}

    def fake_llm(system_prompt, user_prompt):
        captured["system_prompt"] = system_prompt
        return {
            "pertinent": True, "categorie": "CAT_TEST", "score": 80,
            "raison": "test", "description": "test",
            "budget_detecte": None, "duree_execution": None,
            "montant_cautionnement": None, "type_marche": None,
            "procedure_passation": None, "region_execution": None,
            "date_debut_execution": None, "date_ouverture_offres": None,
            "lieu_ouverture_offres": None, "caractere_prix": None,
        }

    monkeypatch.setattr(ai_filter_and_extract, "call_local_llm_json", fake_llm)

    categories = {"CAT_TEST": {"marques": ["MARQUE_TEST"], "keywords": ["mot"], "commercial": "Test"}}
    result = ai_filter_and_extract.filter_and_extract("Objet test", categories)

    assert "CAT_TEST" in captured["system_prompt"]
    assert "MARQUE_TEST" in captured["system_prompt"]
    assert result["pertinent"] is True
    assert result["categorie"] == "CAT_TEST"


def test_filter_and_extract_rejects_unknown_ai_category(monkeypatch):
    def fake_llm(system_prompt, user_prompt):
        return {"pertinent": True, "categorie": "INVENTEE", "score": 90, "raison": "test", "description": "test"}

    monkeypatch.setattr(ai_filter_and_extract, "call_local_llm_json", fake_llm)

    result = ai_filter_and_extract.filter_and_extract("Test", {"CAT_OK": {"marques": [], "keywords": [], "commercial": None}})

    assert result["pertinent"] is False
    assert result["categorie"] is None
    assert result["score"] == 0