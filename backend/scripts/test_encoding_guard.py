"""Vérifie l'encodage des sources Python et les messages français ciblés."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _python_sources():
    return list((ROOT / "app").rglob("*.py")) + list(
        (ROOT / "scripts").glob("*.py")
    )


def test_sources_python_utf8_sans_bom_ni_caractere_de_remplacement():
    problems = []

    for path in _python_sources():
        raw = path.read_bytes()

        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{path.relative_to(ROOT)} : BOM UTF-8")

        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            problems.append(
                f"{path.relative_to(ROOT)} : UTF-8 invalide à l'octet {exc.start}"
            )
            continue

        if "\ufffd" in text:
            problems.append(
                f"{path.relative_to(ROOT)} : caractère U+FFFD présent"
            )

    assert not problems, "\n".join(problems)


def test_messages_tenders_conservent_leurs_accents():
    text = (ROOT / "app/api/tenders.py").read_text(encoding="utf-8")

    expected = (
        "March\u00e9 introuvable",
        "r\u00e9serv\u00e9 aux clients",
        "isolation compl\u00e8te",
        "Rep\u00eachage",
        "D\u00c9CISION",
        "prot\u00e8ge",
    )
    missing = [message for message in expected if message not in text]

    assert not missing, f"Messages accentués absents ou altérés : {missing}"


def test_messages_buyers_conservent_leurs_accents():
    text = (ROOT / "app/api/buyers.py").read_text(encoding="utf-8")

    expected = (
        "Format non support\u00e9",
        "d\u00e9compress\u00e9",
        "rattach\u00e9 \u00e0 une entreprise",
    )
    missing = [message for message in expected if message not in text]

    assert not missing, f"Messages accentués absents ou altérés : {missing}"
