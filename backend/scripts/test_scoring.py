from app.services.keyword_classifier import score_for_category, needs_ai_fallback
from app.schemas.sotradies import SotradiesRaw

def test_keyword_exclusion_returns_zero():
    tender = SotradiesRaw(
        objet="Achat de fournitures de bureau et papeterie",
        acheteur="Commune",
        source="onmp",
        lien="http"
    )
    score, matches = score_for_category(tender, "MATERIEL_ROULANT", {}, ["papeterie"])
    assert score == 0
    assert len(matches) == 0

def test_keyword_match_returns_score():
    tender = SotradiesRaw(
        objet="Acquisition d'un tractopelle neuf",
        acheteur="Commune",
        source="onmp",
        lien="http"
    )
    categories = {"ENGINS_TP": {"keywords": ["tractopelle", "chargeuse"]}}
    score, matches = score_for_category(tender, "ENGINS_TP", categories, [])
    assert score >= 60
    assert "tractopelle" in matches

def test_needs_ai_fallback_true_if_ambiguous():
    tender = SotradiesRaw(
        objet="Acquisition d'engins de chantier divers",
        acheteur="Commune",
        source="onmp",
        lien="http"
    )
    categories = {"ENGINS_TP": {"keywords": ["tractopelle", "chantier"]}}
    score_details = {"ENGINS_TP": {"score": 0}} 
    
    assert needs_ai_fallback(tender, score_details, categories, []) is True

def test_needs_ai_fallback_false_if_already_scored():
    tender = SotradiesRaw(
        objet="Acquisition d'un tractopelle neuf",
        acheteur="Commune",
        source="onmp",
        lien="http"
    )
    score_details = {"ENGINS_TP": {"score": 60}} 
    assert needs_ai_fallback(tender, score_details, {}, []) is False

def test_needs_ai_fallback_false_if_excluded():
    tender = SotradiesRaw(
        objet="Achat de fournitures (stylos, papeterie)",
        acheteur="Commune",
        source="onmp",
        lien="http"
    )
    score_details = {"ENGINS_TP": {"score": 0}} 
    assert needs_ai_fallback(tender, score_details, {}, ["papeterie"]) is False