r"""F-032 : autorise Google Fonts dans la CSP. Simulation par défaut, --apply pour écrire."""
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "main.py"
s = p.read_text(encoding="utf-8-sig")
new = s.replace("\"style-src 'self' 'unsafe-inline'; \"",
                "\"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; \"", 1)
new = new.replace("\"font-src 'self'; \"",
                  "\"font-src 'self' https://fonts.gstatic.com; \"", 1)
print("style-src :", "OK" if "fonts.googleapis.com" in new else "NON TROUVÉ")
print("font-src  :", "OK" if "fonts.gstatic.com" in new else "NON TROUVÉ")
if "--apply" in sys.argv and new != s:
    p.with_suffix(".py.bak13").write_text(s, encoding="utf-8")
    p.write_text(new, encoding="utf-8")
    print("ÉCRIT (copie main.py.bak13).")
else:
    print("SIMULATION : rien n'a été écrit.")