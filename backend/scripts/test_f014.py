import app.api.auth as auth


def test_blocage_par_ip_et_non_par_compte(monkeypatch):
    monkeypatch.setattr(auth, "_redis", lambda: None)
    auth._mem_fails.clear()
    for _ in range(auth.MAX_ATTEMPTS):
        auth._register_failure("a@b.tn", "1.1.1.1")
    assert auth._fail_count("a@b.tn", "1.1.1.1") >= auth.MAX_ATTEMPTS
    assert auth._fail_count("a@b.tn", "2.2.2.2") == 0


def test_reset_apres_succes(monkeypatch):
    monkeypatch.setattr(auth, "_redis", lambda: None)
    auth._register_failure("c@d.tn", "1.1.1.1")
    auth._reset_failures("c@d.tn", "1.1.1.1")
    assert auth._fail_count("c@d.tn", "1.1.1.1") == 0
