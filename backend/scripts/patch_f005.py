r"""
F-005 : vérifie l'adresse avant CHAQUE requête httpx (redirections comprises).
Simulation :  python scripts\patch_f005.py
Appliquer :   python scripts\patch_f005.py --apply   (copie .bak)
"""
import ast
import re
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "services" / "scrapers" / "universal_scraper.py"
raw = p.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
src = raw.decode("utf-8-sig")

if "def _check_request" in src:
    sys.exit("Déjà corrigé (_check_request existe).")

fn = next((n for n in ast.parse(src).body
           if isinstance(n, ast.FunctionDef) and n.name == "_is_safe_url"), None)
if fn is None:
    sys.exit("_is_safe_url introuvable : arrêt, envoie-moi ce message.")

HOOK = '''

def _check_request(request) -> None:
    """F-005 : appelé par httpx avant CHAQUE requête, redirections comprises."""
    if not _is_safe_url(str(request.url)):
        raise httpx.RequestError(f"URL bloquée (adresse interne) : {request.url}", request=request)
'''
lines = src.splitlines(keepends=True)
lines.insert(fn.end_lineno, HOOK)
new = "".join(lines)

new, n = re.subn(
    r"httpx\.Client\(follow_redirects=True,\s*timeout=timeout\)",
    'httpx.Client(follow_redirects=True, timeout=timeout,\n'
    '                          event_hooks={"request": [_check_request]})',
    new,
)
compile(new, str(p), "exec")
print(f"_check_request ajouté après _is_safe_url ; clients httpx protégés : {n}")
if n == 0:
    sys.exit("Aucun httpx.Client trouvé avec ce format : arrêt, envoie-moi ce message.")

if "--apply" in sys.argv:
    p.with_suffix(".py.bak").write_bytes(raw)
    p.write_text(new, encoding="utf-8-sig" if bom else "utf-8", newline="")
    print("ÉCRIT (copie .bak).")
else:
    print("SIMULATION : rien n'a été écrit.")