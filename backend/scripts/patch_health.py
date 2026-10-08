r"""
F-023 : supprime l'ancienne route /health statique (health_check) de app/main.py.
Simulation par défaut :  python scripts\patch_health.py
Appliquer :              python scripts\patch_health.py --apply   (copie main.py.bak)
"""
import re
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "main.py"
raw = p.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
s = raw.decode("utf-8-sig")

# Bloc : @app.get("/health", tags=["health"]) + def health_check(): ... jusqu'au "}" fermant
pattern = re.compile(
    r'@app\.get\("/health",\s*tags=\["health"\]\)\s*\n'
    r'def health_check\(\):\s*\n'
    r'.*?\n\s*\}\s*\n',
    re.S,
)
new, n = pattern.subn("", s, count=1)

# Remettre le tag sur la route restante
if n:
    new = new.replace('@app.get("/health")\n', '@app.get("/health", tags=["health"])\n', 1)

print(f"Ancienne route supprimée : {'oui' if n else 'non trouvée'}")
print(f"Routes /health restantes : {new.count('@app.get(\"/health\"')}")

if "--apply" in sys.argv and n:
    p.with_suffix(".py.bak").write_bytes(raw)
    p.write_text(new, encoding="utf-8-sig" if bom else "utf-8", newline="")
    print("ÉCRIT (copie main.py.bak créée).")
else:
    print("SIMULATION : rien n'a été écrit." if n else "Rien à faire.")