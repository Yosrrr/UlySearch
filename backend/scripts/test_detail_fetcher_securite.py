import httpx

import app.services.detail_fetcher as d


def _interdit(*a, **k):
    raise AssertionError("Playwright ne doit pas être appelé")


def test_adresse_interne_refusee_sans_requete(monkeypatch):
    monkeypatch.setattr(d, "_fetch_html", _interdit)
    monkeypatch.setattr(d, "_fetch_dynamic_body_text", _interdit)
    assert d.fetch_universal_detail_text("http://127.0.0.1/x") == ""


def test_page_404_jamais_renvoyee(monkeypatch):
    def erreur_404(lien, timeout=25):
        req = httpx.Request("GET", lien)
        raise httpx.HTTPStatusError("404", request=req, response=httpx.Response(404, request=req))
    monkeypatch.setattr(d, "_is_safe", lambda u: True)
    monkeypatch.setattr(d, "_fetch_html", erreur_404)
    monkeypatch.setattr(d, "_fetch_dynamic_body_text", _interdit)
    assert d.fetch_universal_detail_text("https://exemple.tn/ao/1") == ""


def test_redirection_bloquee_sans_repli_navigateur(monkeypatch):
    def bloque(lien, timeout=25):
        raise httpx.RequestError("URL bloquée (adresse interne) : http://169.254.169.254/")
    monkeypatch.setattr(d, "_is_safe", lambda u: True)
    monkeypatch.setattr(d, "_fetch_html", bloque)
    monkeypatch.setattr(d, "_fetch_dynamic_body_text", _interdit)
    assert d.fetch_universal_detail_text("https://exemple.tn/ao/1") == ""