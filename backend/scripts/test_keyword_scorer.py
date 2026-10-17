"""Tests de regression du matcher de mots-cles (TECH-002).

API reelle de app.services.keyword_scorer :
- normalize_text(value) -> str
- contains_keyword(text, keyword) -> bool
- first_matching_keyword(text, keywords) -> str | None
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.keyword_scorer import (
    contains_keyword,
    first_matching_keyword,
    normalize_text,
)


# -- normalize_text ---------------------------------------------------------

def test_normalize_minuscules_et_accents():
    assert normalize_text("Matériel ÉLECTRIQUE") == "materiel electrique"

def test_normalize_ponctuation_et_espaces():
    assert normalize_text("pompes,  à-eau !") == "pompes a eau"

def test_normalize_none_et_vide():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""

def test_normalize_non_str():
    assert normalize_text(123) == "123"


# -- contains_keyword -------------------------------------------------------

def test_mot_entier_present():
    assert contains_keyword("Fourniture de pompes hydrauliques", "pompe") is True

def test_pas_de_faux_positif_sous_chaine():
    # "pile" ne doit pas matcher dans "compilation"
    assert contains_keyword("compilation des rapports", "pile") is False

def test_pluriels_geres():
    assert contains_keyword("acquisition de camions", "camion") is True
    assert contains_keyword("travaux de voiries", "voirie") is True

def test_accents_insensibles():
    assert contains_keyword("matériel électrique", "materiel electrique") is True

def test_keyword_multi_mots():
    assert contains_keyword("appel d'offres : génie civil et VRD", "genie civil") is True

def test_keyword_absent():
    assert contains_keyword("construction d'un pont", "informatique") is False

def test_keyword_non_str_retourne_false():
    assert contains_keyword("texte quelconque", None) is False
    assert contains_keyword("texte quelconque", 42) is False

def test_texte_vide():
    assert contains_keyword("", "pompe") is False
    assert contains_keyword(None, "pompe") is False


# -- first_matching_keyword -------------------------------------------------

def test_premier_match_retourne():
    kws = ["informatique", "pompe", "camion"]
    assert first_matching_keyword("achat de pompes et camions", kws) == "pompe"

def test_aucun_match_retourne_none():
    assert first_matching_keyword("construction d'un pont", ["informatique"]) is None

def test_liste_vide_retourne_none():
    assert first_matching_keyword("n'importe quoi", []) is None