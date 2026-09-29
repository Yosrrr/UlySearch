"""
Teste les collecteurs sélectionnés par le pipeline.

Ce script :
- lit la configuration des sources ;
- appelle directement fetch_tenders(), sans le cache du pipeline ;
- affiche quelques annonces ;
- n'insère aucun marché ;
- n'appelle aucun notifier.
"""

from app.services.pipeline import _build_scrapers


def main() -> int:
    scrapers = _build_scrapers()

    if not scrapers:
        print("Aucune source active avec abonnement actif.")
        return 1

    failures = 0
    summary = []

    for scraper in scrapers:
        name = scraper.source_name

        print()
        print("=" * 70)
        print(f"TEST DE COLLECTE : {name}")
        print("=" * 70)

        try:
            tenders = list(scraper.fetch_tenders() or [])

            summary.append((name, len(tenders), None))
            print(f"Annonces retournees : {len(tenders)}")

            if not tenders:
                print(
                    "Aucune annonce retournee. "
                    "Verifier les logs et la page avant de conclure."
                )

            for tender in tenders[:3]:
                print()
                print("Objet       :", tender.objet)
                print("Reference   :", tender.reference)
                print("Publication :", tender.date_publication)
                print("Echeance    :", tender.date_limite)
                print("Lien        :", tender.lien)

        except Exception as exc:
            failures += 1
            summary.append((name, None, str(exc)))
            print(f"ERREUR : {type(exc).__name__}: {exc}")

    print()
    print("=" * 70)
    print("RESUME DES RETOURS DES COLLECTEURS")
    print("=" * 70)

    for name, count, error in summary:
        if error is not None:
            print(f"{name}: erreur — {error}")
        else:
            print(f"{name}: {count} annonce(s) retournee(s)")

    print()
    print(
        "Le nombre retourne ne prouve pas que toutes les annonces "
        "sont completes, ouvertes ou pertinentes."
    )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())