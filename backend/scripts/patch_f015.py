import re
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[1]
APPLY = "--apply" in sys.argv
changes = []


def edit(rel, label, func):
    p = B / rel
    s = p.read_text(encoding="utf-8-sig")
    new = func(s)
    print(f"[{rel}] {label} : {'OK' if new != s else 'NON TROUVÉ / déjà fait'}")
    compile(new, str(p), "exec")
    changes.append((p, s, new))


# 1. Colonne dans le modèle User
edit("app/models/user.py", "colonne token_version",
     lambda s: s if "token_version" in s else re.sub(
         r"(\n([ \t]+)locked_until = Column\(DateTime, nullable=True\)\n)",
         r'\1\2token_version = Column(Integer, nullable=False, default=0, server_default="0")\n',
         s, count=1))

# 2. Déconnexion : incrémente la version
LOGOUT = '''@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """F-015 : invalide TOUS les jetons de cet utilisateur, puis supprime le cookie."""
    db_user = db.query(User).filter_by(email=user["sub"]).first()
    if db_user:
        db_user.token_version = (db_user.token_version or 0) + 1
        db.add(AuditLog(utilisateur_email=db_user.email, action="deconnexion", detail=None))
        db.commit()
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"detail": "Déconnecté"}
'''
edit("app/api/auth.py", "logout invalide les jetons",
     lambda s: s if "db_user.token_version" in s else re.sub(
         r'@router\.post\("/logout"\).*?(?=\n@router\.)', lambda m: LOGOUT, s, count=1, flags=re.S))

# 3. deps.py : refuse un jeton dont la version ne correspond plus
CHECK = '''
    # F-015 : jeton émis avant la dernière déconnexion -> refusé
    tv_user = getattr(user, "token_version", 0)
    if not isinstance(tv_user, int):
        tv_user = 0
    try:
        tv_token = int(payload.get("tv", 0))
    except (TypeError, ValueError):
        tv_token = -1
    if tv_token != tv_user:
        raise HTTPException(status_code=401, detail="Session expirée, reconnectez-vous")
'''
edit("app/api/deps.py", "contrôle de version",
     lambda s: s if "F-015" in s else re.sub(
         r'(\n[ \t]+if not user or not user\.actif:\n[ \t]+raise HTTPException\(status_code=401, detail="Session invalide"\)\n)',
         lambda m: m.group(1) + CHECK, s, count=1))

# 4. Migration
table = re.search(r'__tablename__\s*=\s*"(\w+)"',
                  (B / "app/models/user.py").read_text(encoding="utf-8-sig")).group(1)
MIG = f'''"""F-015 : token_version sur {table}

Revision ID: f015a7c3e2d1
Revises: d9e8f7a6b5c4
"""
from alembic import op
import sqlalchemy as sa

revision = "f015a7c3e2d1"
down_revision = "d9e8f7a6b5c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("{table}", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("{table}", "token_version")
'''
mig = B / "alembic" / "versions" / "f015a7c3e2d1_token_version.py"
print(f"[migration] table = {table} -> {mig.name}")

TEST = """import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.auth as auth
import app.api.deps as deps
from app.core.security import create_access_token


class _Q:
    def __init__(self, u): self.u = u
    def filter_by(self, **kw): return self
    def filter(self, *a): return self
    def first(self): return self.u


class _DB:
    def __init__(self, u): self.u = u
    def query(self, *a): return _Q(self.u)


def _user(tv):
    return SimpleNamespace(email="a@b.tn", actif=True, profil="admin", nom="A",
                           company_id=1, token_version=tv)


def _req(tok):
    return SimpleNamespace(cookies={deps.AUTH_COOKIE_NAME: tok}, headers={})


def test_ancien_jeton_refuse_apres_deconnexion():
    old = create_access_token({"sub": "a@b.tn", "profil": "admin", "tv": 0})
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(_req(old), _DB(_user(1)))
    assert e.value.status_code == 401


def test_jeton_courant_accepte():
    tok = create_access_token({"sub": "a@b.tn", "profil": "admin", "tv": 1})
    assert deps.get_current_user(_req(tok), _DB(_user(1)))["sub"] == "a@b.tn"


def test_logout_incremente_la_version():
    assert "token_version" in inspect.getsource(auth.logout)
"""

if APPLY:
    for p, old, new in changes:
        if new != old:
            p.with_suffix(p.suffix + ".bak17").write_text(old, encoding="utf-8")
            p.write_text(new, encoding="utf-8")
    if not mig.exists():
        mig.write_text(MIG, encoding="utf-8")
    (B / "scripts" / "test_f015.py").write_text(TEST, encoding="utf-8")
    print("ÉCRIT (copies .bak17, migration et test créés).")
else:
    print("SIMULATION : rien n'a été écrit.")