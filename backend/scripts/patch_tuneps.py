r"""
Corrige 3 points (simulation par défaut) :
  1. tuneps_scraper.py : supprime l'envoi des identifiants (TLS non vérifié)
  2. requirements.txt  : playwright==1.62.0 (1.49.1 est incompatible avec scrapling)
  3. Dockerfile        : supprime les lignes playwright/mkdir en double APRÈS "USER pwuser"
Usage : python scripts\patch_tuneps_deps.py           (simulation)
        python scripts\patch_tuneps_deps.py --apply   (écrit, avec copie .bak)
"""
import re
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[1]   # backend
R = B.parent                              # racine
APPLY = "--apply" in sys.argv


def save(path: Path, raw: bytes, text: str) -> None:
    bom = raw.startswith(b"\xef\xbb\xbf")
    path.with_suffix(path.suffix + ".bak").write_bytes(raw)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8", newline="")


# 1. TUNEPS
p = B / "app" / "services" / "scrapers" / "tuneps_scraper.py"
raw = p.read_bytes(); s = raw.decode("utf-8-sig")
new = re.sub(
    r'\n[ \t]*token = base64\.b64encode\(.*?headers\["Authorization"\] = f"Basic \{token\}"',
    "", s, flags=re.S)
print(f"[1] tuneps : {'envoi des identifiants supprimé' if new != s else 'rien trouvé (déjà corrigé ?)'}")
if APPLY and new != s:
    save(p, raw, new)

# 2. requirements.txt
p = B / "requirements.txt"
raw = p.read_bytes(); s = raw.decode("utf-8-sig")
new = re.sub(r"(?m)^playwright\s*[=<>!~]=?\s*[\d.]+\s*$", "playwright==1.62.0", s)
print(f"[2] requirements : {'playwright -> 1.62.0' if new != s else 'déjà correct'}")
if APPLY and new != s:
    save(p, raw, new)

# 3. Dockerfile
p = R / "Dockerfile"
raw = p.read_bytes(); s = raw.decode("utf-8-sig")
lines = s.splitlines(keepends=True)
idx = next((i for i, l in enumerate(lines) if l.strip().startswith("USER ")), None)
removed = []
if idx is not None:
    kept = lines[: idx + 1]
    for l in lines[idx + 1:]:
        t = l.strip()
        if (t.startswith("ENV PLAYWRIGHT_BROWSERS_PATH") or "playwright install" in t
                or t.startswith("RUN mkdir -p /app/data")):
            removed.append(t)
        else:
            kept.append(l)
    new = "".join(kept)
else:
    new = s
print(f"[3] Dockerfile : lignes supprimées après USER = {removed or 'aucune'}")
if APPLY and new != s:
    save(p, raw, new)

print("\nÉCRIT (copies .bak créées)." if APPLY else "\nSIMULATION : rien n'a été écrit. Relance avec --apply.")