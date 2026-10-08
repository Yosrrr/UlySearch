import pytest

from app.services.keyword_matcher import match_keywords

TROUVES = [
    ("Acquisition de groupes électrogènes", "groupe electrogene"),
    ("Acquisition d'un groupe électrogène", "groupes electrogenes"),
    ("Entretien des installations électriques", "installation electrique"),
    ("Fourniture de climatiseurs", "climatiseur"),
    ("Fourniture de pompes à chaleur", "pompe à chaleur"),
    ("اقتناء المكيفات لفائدة المستشفى", "مكيف"),
    ("اقتناء وتركيب تجهيزات طبية", "تجهيزات طبية"),
    ("اقتناء المولدات الكهربائية", "مولد كهربائي"),
    ("إقتناء مولدات كهربائية", "اقتناء مولد كهربائي"),
    ("Fourniture de splits DAIKIN", "Daikin"),
    ("Acquisition d'un système intégré (ERP)", "ERP"),
]

REFUSES = [
    ("Étude sur le changement climatique", "clim"),
    ("Réunion du groupe de travail", "groupe electrogene"),
    ("Construction d'un mur de clôture", "climatiseur"),
    ("تهيئة و صيانة المدارس الابتدائية", "صيانة الشبكات المعلوماتية"),
]


@pytest.mark.parametrize("texte,kw", TROUVES)
def test_trouve(texte, kw):
    assert match_keywords(texte, [kw]) == [kw]


@pytest.mark.parametrize("texte,kw", REFUSES)
def test_refuse(texte, kw):
    assert match_keywords(texte, [kw]) == []
    
    
def test_variantes_comptees_une_seule_fois():
    kws = ["systeme information", "système information", "systeme information",
           "entretien engin", "entretien engins"]
    texte = "Entretien des engins et système d'information"
    assert match_keywords(texte, kws) == ["systeme information", "entretien engin"]