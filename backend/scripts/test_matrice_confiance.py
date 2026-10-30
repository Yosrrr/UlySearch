"""Matrice de décision : confiance IA x mot-clé de la catégorie retenue."""
from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest

from app.core.config import settings
from app.services import ai_scorer
from app.services import scoring_orchestrator as orch
from app.services.scoring_orchestrator import (
    SCORE_HAUTE_AVEC_MOT_CLE,
    SCORE_RETENU_SANS_ALERTE,
)

CATS = {
    "peinture_industrielle": {
        "label": "Peinture industrielle",
        "keywords": ["peinture industrielle", "anticorrosion", "epoxy"],
        "marques": [],
    },
    "nettoyage_industriel": {
        "label": "Nettoyage industriel",
        "keywords": ["nettoyage industriel"],
        "marques": [],
    },
}
EXCL = ["fourniture de bureau"]
CAT = "peinture_industrielle"


@pytest.fixture(autouse=True)
def _etat(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    orch.reset_cache()
    ai_scorer.reset_circuit()
    yield
    orch.reset_cache()
    ai_scorer.reset_circuit()


def _offre(objet, categorie=None, description=None):
    return SimpleNamespace(
        objet=objet, categorie=categorie, acheteur="Mairie",
        description_detaillee=description, type_marche=None,
    )


def _verdict(categorie, confiance, raison="motif"):
    return {"erreur": False, "categorie": categorie, "confiance": confiance, "raison": raison}


@pytest.mark.parametrize(
    "confiance, objet, score_attendu, methode_attendue",
    [
        ("haute", "Travaux anticorrosion de cuves", 85, "ia"),
        ("haute", "Revêtement protecteur des structures métalliques", 0, "non_retenu"),  # sans mot-clé : porte fermée
        ("moyenne", "Lot 3 : travaux anticorrosion", 65, "ia"),
        ("moyenne", "Lot 3 : divers travaux", 0, "non_retenu"),
        ("faible", "Achat de résine epoxy pour atelier manuel", 0, "ia_rejet"),       # mot-clé epoxy, IA faible
        ("faible", "Équipement des centres forestiers", 0, "non_retenu"),
    ],
)
def test_matrice(confiance, objet, score_attendu, methode_attendue):
    with patch.object(orch, "AI_REVIEW_WITHOUT_KEYWORD", False), \
         patch.object(orch, "juger_marche", return_value=_verdict(CAT, confiance)):
        result = orch.score_tender_full(_offre(objet), CATS, EXCL)
    assert result[CAT]["score"] == score_attendu
    assert result[CAT]["methode"] == methode_attendue


def test_mot_generique_ne_suffit_pas():
    """« peinture » seule ≠ « peinture industrielle » : aucun mot-clé, porte fermée, l'IA n'est même pas appelée."""
    with patch.object(orch, "AI_REVIEW_WITHOUT_KEYWORD", False), patch.object(orch, "juger_marche") as ia:
        result = orch.score_tender_full(_offre("Achat de peinture pour bureaux"), CATS, EXCL)
    ia.assert_not_called()
    assert result[CAT]["score"] == 0 and result[CAT]["methode"] == "non_retenu"


def test_mot_cle_d_une_autre_categorie_retenu_sans_alerte():
    """Mot-clé dans nettoyage_industriel, IA choisit peinture : retenu 65 sous la catégorie du mot-clé,
    catégorie IA tracée, pas d'alerte (c'est le cas « محولات كهربائية » qui était perdu)."""
    offre = _offre("Nettoyage industriel et remise en peinture des cuves")
    with patch.object(orch, "juger_marche", return_value=_verdict(CAT, "haute")):
        result = orch.score_tender_full(offre, CATS, EXCL)
    d = result["nettoyage_industriel"]
    assert d["score"] == 65 and d["preuve"] == "recategorisation" and d["categorie_ia"] == CAT
    assert result[CAT]["score"] == 0

def test_faute_de_frappe_reconnue_comme_mot_cle():
    with patch.object(orch, "juger_marche", return_value=_verdict(CAT, "haute")):
        result = orch.score_tender_full(
            _offre("Travaux de penture industreille pour hangars"), CATS, EXCL
        )
    assert result[CAT]["score"] == SCORE_HAUTE_AVEC_MOT_CLE
    assert result[CAT]["mots_cles_matches"]



def test_mot_cle_dans_la_description_compte():
    offre = _offre(
        "Revêtement de cuves",
        description="Application d'un revêtement anticorrosion epoxy.",
    )
    with patch.object(orch, "juger_marche", return_value=_verdict(CAT, "haute")):
        result = orch.score_tender_full(offre, CATS, EXCL)
    assert result[CAT]["score"] == SCORE_HAUTE_AVEC_MOT_CLE
    assert result[CAT]["mots_cles_matches"], "le mot-clé de la description doit être tracé"

def test_mot_cle_d_une_autre_categorie_ne_compte_pas():
    offre = _offre("Nettoyage industriel et remise en peinture des cuves")
    with patch.object(orch, "juger_marche", return_value=_verdict(CAT, "haute")):
        result = orch.score_tender_full(offre, CATS, EXCL)
    assert result[CAT]["score"] == 0


def test_mot_cle_seul_ne_decide_pas():
    offre = _offre("Achat de résine epoxy pour atelier manuel")
    with patch.object(orch, "juger_marche", return_value=_verdict(None, "faible", "Usage artistique.")):
        result = orch.score_tender_full(offre, CATS, EXCL)
    assert result[CAT]["score"] == 0
    assert result[CAT]["methode"] == "ia_rejet"


def test_rejet_faible_explique_le_motif():
    offre = _offre("Achat de résine epoxy pour atelier manuel")
    with patch.object(orch, "juger_marche", return_value=_verdict(CAT, "faible", "Usage artistique.")):
        result = orch.score_tender_full(offre, CATS, EXCL)
    assert "faible" in result[CAT]["raison_ia"]
    assert "Usage artistique." in result[CAT]["raison_ia"]


def test_exclusion_avant_ia():
    with patch.object(orch, "juger_marche") as juger:
        result = orch.score_tender_full(_offre("Achat de fourniture de bureau"), CATS, EXCL)
    juger.assert_not_called()
    assert result[CAT]["methode"] == "exclusion"


def test_seuils_d_alerte():
    assert SCORE_HAUTE_AVEC_MOT_CLE >= 70
    assert SCORE_RETENU_SANS_ALERTE < 70


def test_identifiants_remplaces_par_des_codes_pour_l_ia():
    """Le modèle ne voit jamais les identifiants : codes C1/C2 transmis, verdict décodé, raison lisible."""
    capture = {}

    def faux_juger(marche, client):
        capture["client"] = client
        capture["code"] = next(c for c, d in client["categories"].items() if d["label"] == "Peinture industrielle")
        return {"pertinent": True, "categorie": capture["code"], "confiance": "haute",
                "raison": f"Travaux anticorrosion : correspond à {capture['code']}."}

    with patch.object(orch, "juger_marche", side_effect=faux_juger):
        result = orch.score_tender_full(_offre("Travaux anticorrosion de cuves"), CATS, EXCL)

    assert set(capture["client"]["categories"]) == {"C1", "C2"}
    assert CAT not in json.dumps(capture["client"], ensure_ascii=False)
    assert result[CAT]["score"] == SCORE_HAUTE_AVEC_MOT_CLE and result[CAT]["methode"] == "ia"
    assert "Peinture industrielle" in result[CAT]["raison_ia"] and capture["code"] not in result[CAT]["raison_ia"]
@pytest.fixture(autouse=True)
def _ia_activee(monkeypatch):
    """Les tests simulent l'IA (juger_marche mocké) : LLM_ENABLED doit être vrai pour les atteindre."""
    monkeypatch.setattr(orch.settings, "LLM_ENABLED", True)


def test_ia_desactivee_mot_cle_retenu_et_visible(monkeypatch):
    """LLM_ENABLED=false (production sans Ollama) : une offre à mot-clé reste RETENUE et visible
    (60 : au-dessus du seuil, sous l'alerte), aucun appel IA, jamais a_verifier."""
    monkeypatch.setattr(orch.settings, "LLM_ENABLED", False)
    with patch.object(orch, "juger_marche") as ia:
        result = orch.score_tender_full(_offre("Travaux anticorrosion de cuves"), CATS, EXCL)
    ia.assert_not_called()
    d = result[CAT]
    assert d["methode"] == orch.METHODE_REGLES_SANS_IA and 50 <= d["score"] < 70
    assert not any(x["methode"] == "a_verifier" for x in result.values())
def test_ia_en_panne_mot_cle_retenu_provisoirement():
    """Option B : IA indisponible + mot-clé -> a_verifier à 60 (visible, retenu, pas d'alerte),
    non mis en cache ; au retour de l'IA, son verdict s'applique."""
    panne = {"erreur": True, "pertinent": False, "categorie": None, "score": 0, "raison": "Erreur technique IA (locale)"}
    with patch.object(orch, "juger_marche", side_effect=[panne, _verdict(CAT, "haute")]) as ia:
        d1 = orch.score_tender_full(_offre("Travaux anticorrosion de cuves"), CATS, EXCL)
        d2 = orch.score_tender_full(_offre("Travaux anticorrosion de cuves"), CATS, EXCL)
    assert ia.call_count == 2                                            # le provisoire n'est pas mis en cache
    assert d1[CAT]["methode"] == orch.METHODE_A_VERIFIER and d1[CAT]["score"] == orch.SCORE_SANS_IA
    assert d1[CAT]["provisoire"] is True and d1[CAT]["mots_cles_matches"]
    assert all(x["methode"] == orch.METHODE_NON_RETENU for c, x in d1.items() if c != CAT)
    assert d2[CAT]["methode"] == "ia" and d2[CAT]["score"] == 85


def test_ia_en_panne_sans_mot_cle_non_retenu(monkeypatch):
    """IA indisponible sans mot-clé (rattrapage activé) : non retenu, jamais un provisoire à 0."""
    monkeypatch.setattr(orch, "AI_REVIEW_WITHOUT_KEYWORD", True)
    panne = {"erreur": True, "pertinent": False, "categorie": None, "score": 0, "raison": "Erreur technique IA (locale)"}
    with patch.object(orch, "juger_marche", return_value=panne):
        result = orch.score_tender_full(_offre("Achat de peinture pour bureaux"), CATS, EXCL)
    assert all(x["methode"] == orch.METHODE_NON_RETENU for x in result.values())
