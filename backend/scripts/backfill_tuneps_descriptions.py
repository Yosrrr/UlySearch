"""
Backfill des descriptions TUNEPS existantes.

But :
- ne pas supprimer les marchés ;
- ne pas casser les FK audit_log / sent_log ;
- remplir description_detaillee quand elle est None ou vide.
"""

from app.core.database import session_scope
from app.models.sotradies import Sotradies


def _clean_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    text = text.replace("..", ".")
    text = text.replace(" ,", ",")
    text = text.replace(" .", ".")
    text = text.replace(" ;", ";")
    text = text.replace(" :", ":")
    return text.strip()


def build_description(t: Sotradies) -> str:
    date_limite_txt = (
        t.date_limite.strftime("%d/%m/%Y")
        if t.date_limite
        else "non communiquée"
    )

    objet = _clean_sentence(t.objet or "ce marché")
    acheteur = _clean_sentence(t.acheteur or "l'acheteur public")

    return _clean_sentence(
        f"Cet appel d'offres concerne {objet}. "
        f"L'acheteur public est {acheteur}. "
        f"La date limite de réception des offres est {date_limite_txt}."
    )


def main() -> None:
    with session_scope() as db:
        rows = (
            db.query(Sotradies)
            .filter(Sotradies.source == "tuneps")
            .filter(
                (Sotradies.description_detaillee.is_(None))
                | (Sotradies.description_detaillee == "")
            )
            .all()
        )

        for tender in rows:
            tender.description_detaillee = build_description(tender)

        print(f"Descriptions TUNEPS complétées : {len(rows)}")


if __name__ == "__main__":
    main()