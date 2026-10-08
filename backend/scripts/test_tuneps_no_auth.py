import app.services.scrapers.tuneps_scraper as t


class _Resp:
    status = 200
    def json(self):
        return {"payload": {"data": [], "total": 0}}


def _capture(monkeypatch):
    sent = {}
    def fake_post(url, **kw):
        sent.update(kw)
        return _Resp()
    monkeypatch.setattr(t.Fetcher, "post", fake_post)
    return sent


def test_defaut_tls_non_verifie_et_aucun_identifiant(monkeypatch):
    monkeypatch.delenv("TUNEPS_SSL_VERIFY", raising=False)
    sent = _capture(monkeypatch)
    t.TunepsScraper(auth=("login", "secret"))._fetch_page(0)
    assert sent["verify"] is False
    assert "Authorization" not in sent["headers"]


def test_pc_client_tls_verifie_alors_identifiants_envoyes(monkeypatch):
    monkeypatch.setenv("TUNEPS_SSL_VERIFY", "true")
    monkeypatch.delenv("TUNEPS_CA_BUNDLE", raising=False)
    sent = _capture(monkeypatch)
    t.TunepsScraper(auth=("login", "secret"))._fetch_page(0)
    assert sent["verify"] is True
    assert sent["headers"]["Authorization"].startswith("Basic ")


def test_une_seule_requete_par_page(monkeypatch):
    calls = []
    monkeypatch.setattr(t.Fetcher, "post", lambda url, **kw: calls.append(1) or _Resp())
    t.TunepsScraper()._fetch_page(0)
    assert len(calls) == 1