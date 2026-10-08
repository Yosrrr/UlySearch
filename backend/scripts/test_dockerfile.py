import re
from pathlib import Path

D = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(encoding="utf-8-sig")
R = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8-sig")


def test_deux_from():
    f = re.findall(r"^FROM\s+(\S+)", D, re.M)
    assert len(f) == 2 and f[0].startswith("node:")


def test_playwright_aligne():
    assert re.search(r"playwright/python:v([\d.]+)", D).group(1) == re.search(r"^playwright==([\d.]+)", R, re.M).group(1)


def test_user_non_root_avant_cmd():
    assert D.index("playwright install") < D.index("USER pwuser") < D.index("CMD [")
