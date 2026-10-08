import io
from pathlib import Path
import pytest

api = pytest.importorskip("pyflakes.api")
from pyflakes.reporter import Reporter


def test_aucun_nom_indefini_dans_app():
    out = io.StringIO()
    api.checkRecursive([str(Path(__file__).resolve().parents[1] / "app")], Reporter(out, io.StringIO()))
    bad = [l for l in out.getvalue().splitlines() if "undefined name" in l]
    assert not bad, "\n".join(bad)
