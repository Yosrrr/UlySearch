"""
Activation contrôlée des sources universelles BAD et UNDP.

Prévisualisation :
    python -m scripts.enable_universal_sources

Application :
    python -m scripts.enable_universal_sources --apply
"""

import argparse

import app.models  # noqa: F401

from app.core.database import session_scope
from app.models.company_source import CompanySource
from app.models.scraping_source import ScrapingSource


# Identifiants observés dans votre base.
SOURCE_IDS = (21, 22)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with session_scope() as db:
        for source_id in SOURCE_IDS:
            source = db.get(ScrapingSource, source_id)

            if source is None:
                raise ValueError(
                    f"Source {source_id} introuvable. "
                    "Aucune nouvelle source ne sera créée."
                )

            if source.type != "universel":
                raise ValueError(
                    f"La source {source_id} n'est pas universelle."
                )

            subscriptions = (
                db.query(CompanySource)
                .filter(
                    CompanySource.source_id == source.id,
                    CompanySource.actif.is_(True),
                )
                .all()
            )

            print()
            print(f"[{source.id}] {source.nom}")
            print(f"URL : {source.url}")
            print(f"Active actuellement : {source.actif}")
            print(f"Navigateur : {source.use_browser}")
            print(f"Pages maximum : {source.max_pages}")
            print(
                "Entreprises abonnées :",
                [subscription.company_id for subscription in subscriptions],
            )

            if not subscriptions:
                print("Aucun abonnement actif : la source ne sera pas collectée.")
                continue

            if args.apply:
                source.actif = True

        if not args.apply:
            print("\nPREVISUALISATION : aucune modification.")

    if args.apply:
        print("\nActivation enregistrée.")


if __name__ == "__main__":
    main()