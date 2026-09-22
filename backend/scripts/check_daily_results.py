"""Vérifie les résultats enregistrés pour une date."""

import sys
from datetime import datetime, timedelta

from app.models import (  # noqa: F401
    commercial,
    company,
    configuration,
    sotradies,
    user,
)
from app.core.database import session_scope
from app.models.sotradies import Sotradies


def main() -> None:
    date_text = (
        sys.argv[1]
        if len(sys.argv) > 1
        else datetime.now().strftime("%Y-%m-%d")
    )

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )
    end = start + timedelta(days=1)

    with session_scope() as db:
        tenders = (
            db.query(Sotradies)
            .filter(
                Sotradies.date_publication >= start,
                Sotradies.date_publication < end,
            )
            .order_by(
                Sotradies.date_publication.desc()
            )
            .all()
        )

        print("=" * 70)
        print(f"MARCHÉS DU {date_text}")
        print("=" * 70)

        print(f"Total : {len(tenders)}")
        print(
            "Retenus :",
            sum(
                1
                for tender in tenders
                if tender.statut == "retenu"
            ),
        )

        sources = {}

        for tender in tenders:
            sources[tender.source] = (
                sources.get(tender.source, 0) + 1
            )

        print("Par source :", sources)
        print()

        for tender in tenders:
            best_score = max(
                (
                    int(details.get("score", 0) or 0)
                    for details
                    in (tender.score_details or {}).values()
                    if isinstance(details, dict)
                ),
                default=0,
            )

            print(
                f"[{tender.source} | "
                f"{tender.statut} | "
                f"{best_score}%] "
                f"{tender.objet[:75]}"
            )

            print(
                "  Catégorie  :",
                tender.categorie or "N/A",
            )
            print(
                "  Commercial :",
                tender.commercial_assigne or "N/A",
            )


if __name__ == "__main__":
    main()