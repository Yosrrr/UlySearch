"""AVAIL-002 / regression : /buyers/import doit rester complet et valide le contenu."""
import ast
import subprocess
import sys
from pathlib import Path

BUYERS = Path(__file__).resolve().parents[1] / "app" / "api" / "buyers.py"


def _import_buyers_body() -> str:
    tree = ast.parse(BUYERS.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "import_buyers")
    return ast.unparse(fn)


def test_import_buyers_appelle_import_known_buyers():
    body = _import_buyers_body()
    assert "import_known_buyers(" in body, "import_buyers ne lance plus l'import (regression NameError)"
    assert "company_id = user.get" in body
    assert "rematch_company_tenders" in body


def test_import_buyers_xlsx_uniquement_et_contenu_valide():
    body = _import_buyers_body()
    assert ".xls'" not in body and ".csv" not in body, ".xls/.csv ne sont pas lus par read_excel"
    assert "zipfile.ZipFile(" in body, "validation du conteneur ZIP/XLSX absente"
    assert "xl/workbook.xml" in body, "verification du classeur Office absente"
    assert "MAX_IMPORT_SIZE" in body, "limite de taille absente"


def test_buyers_pas_de_nom_indefini():
    r = subprocess.run([sys.executable, "-m", "pyflakes", str(BUYERS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
