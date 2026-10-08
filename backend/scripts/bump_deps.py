r"""
F-020 : met à jour les versions corrigées dans requirements.txt (+ retire le BOM).
Simulation : python scripts\bump_deps.py   |   Appliquer : python scripts\bump_deps.py --apply
"""
import re
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "requirements.txt"
raw = p.read_bytes()
s = raw.decode("utf-8-sig")

PINS = {
    "python-dotenv": "1.2.2",
    "jinja2": "3.1.6",
    "requests": "2.33.0",
    "python-multipart": "0.0.31",
    "pytest": "9.0.3",
    "pillow": "12.3.0",
}

new = s
for name, version in PINS.items():
    pattern = re.compile(rf"^({re.escape(name)}(?:\[[^\]]*\])?)\s*[=<>!~]=?\s*[\w.]+\s*$", re.I | re.M)
    new, n = pattern.subn(rf"\g<1>=={version}", new)
    print(f"{name:<18} -> {version}  {'modifié' if n else 'ABSENT du fichier'}")

print("BOM présent :", raw.startswith(b"\xef\xbb\xbf"))
if "--apply" in sys.argv:
    p.with_suffix(".txt.bak10").write_bytes(raw)
    p.write_text(new, encoding="utf-8", newline="")   # sans BOM
    print("ÉCRIT (copie requirements.txt.bak10).")
else:
    print("SIMULATION : rien n'a été écrit.")