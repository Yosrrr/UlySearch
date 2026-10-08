r"""F-014 : blocage par email + IP (simulation par défaut, --apply pour écrire)."""
import ast
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[1]
p = B / "app" / "api" / "auth.py"
s = p.read_text(encoding="utf-8-sig")
if "_register_failure" in s:
    sys.exit("Déjà corrigé.")

HELPERS = '''
# F-014 : compteur d'échecs par (email, IP) — un tiers ne peut plus bloquer le compte.
FAIL_WINDOW_SECONDS = 15 * 60
_mem_fails: dict[str, tuple[int, float]] = {}


def _redis():
    try:
        import redis as _r
        return _r.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
    except Exception:
        return None


def _fail_key(email: str, ip: str) -> str:
    return f"loginfail:{email}:{ip}"


def _fail_count(email: str, ip: str) -> int:
    key = _fail_key(email, ip)
    try:
        return int(_redis().get(key) or 0)
    except Exception:
        n, exp = _mem_fails.get(key, (0, 0.0))
        return n if exp > time.time() else 0


def _register_failure(email: str, ip: str) -> int:
    key = _fail_key(email, ip)
    try:
        r = _redis()
        n = r.incr(key)
        r.expire(key, FAIL_WINDOW_SECONDS)
        return int(n)
    except Exception:
        n = _fail_count(email, ip) + 1
        _mem_fails[key] = (n, time.time() + FAIL_WINDOW_SECONDS)
        return n


def _reset_failures(email: str, ip: str) -> None:
    key = _fail_key(email, ip)
    try:
        _redis().delete(key)
    except Exception:
        pass
    _mem_fails.pop(key, None)

'''

LOGIN = '''@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    ip = request.client.host if request.client else "inconnu"

    if _fail_count(email, ip) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429,
                            detail="Trop de tentatives depuis cet appareil. Réessayez dans 15 minutes.")

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        if _register_failure(email, ip) >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429,
                                detail="Trop de tentatives depuis cet appareil. Réessayez dans 15 minutes.")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.actif:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé.")

    _reset_failures(email, ip)
    user.failed_login_attempts = 0
    user.locked_until = None

    token = create_access_token({"sub": user.email, "profil": user.profil,
                                 "tv": getattr(user, "token_version", 0) or 0})
    db.add(AuditLog(utilisateur_email=user.email, action="connexion", detail=None))
    db.commit()
    _set_auth_cookie(response, token)
    return {"user": {"email": user.email, "nom": user.nom, "profil": user.profil}}
'''

fn = next(n for n in ast.parse(s).body
          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "login")
start = min([d.lineno for d in fn.decorator_list] + [fn.lineno]) - 1
lines = s.splitlines(keepends=True)
new = "".join(lines[:start]) + HELPERS + LOGIN + "".join(lines[fn.end_lineno:])
if "import time" not in new:
    new = "import time\n" + new
if "from sqlalchemy import func" not in new:
    new = "from sqlalchemy import func\n" + new
compile(new, str(p), "exec")
print(f"login remplacée (lignes {start + 1} à {fn.end_lineno}) : OK")

TEST = """import app.api.auth as auth


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
"""

if "--apply" in sys.argv:
    p.with_suffix(".py.bak16").write_text(s, encoding="utf-8")
    p.write_text(new, encoding="utf-8")
    (B / "scripts" / "test_f014.py").write_text(TEST, encoding="utf-8")
    print("ÉCRIT (copie auth.py.bak16, test créé).")
else:
    print("SIMULATION : rien n'a été écrit.")
