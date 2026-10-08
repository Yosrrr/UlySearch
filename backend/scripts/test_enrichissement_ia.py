import app.services.ai_filter_and_extract as m


def test_extraction_appelle_le_modele_meme_sans_categories(monkeypatch):
    appels = []

    def faux_llm(system, user, **kw):
        appels.append(1)
        return {"pertinent": False, "categorie": None, "score": 0, "raison": "ok",
                "description": "Acquisition de climatiseurs.", "budget_detecte": "12000"}

    monkeypatch.setattr(m, "call_local_llm_json", faux_llm)
    r = m.filter_and_extract("Objet : Acquisition de climatiseurs\nAcheteur : STEG", {})
    assert appels, "le modèle n'a pas été appelé"
    assert r["budget_detecte"] == 12000.0