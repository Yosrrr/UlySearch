# scripts/fix_sources.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import session_scope
from app.models.scraping_source import ScrapingSource


# ── URLs RÉELLES de sites tunisiens d'appels d'offres ──
REAL_SOURCES = [
    {
        "nom": "Tunisie Marchés",
        "url": "https://www.tunisiemarches.com/appels-offres",
        "type": "universel",
    },
    {
        "nom": "TED Europa",
        "url": "https://ted.europa.eu/en/search/result?TN-CC=TN",
        "type": "universel",
    },
    {
        "nom": "DGMARKET - Banque Mondiale",
        "url": "https://www.dgmarket.com/tenders/np-notice.do?country=TN",
        "type": "universel",
    },
    {
        "nom": "BAD - Banque Africaine",
        "url": "https://www.afdb.org/fr/projects-and-operations/procurement",
        "type": "universel",
    },
]


def fix_sources():
    with session_scope() as db:
        # 1. Voir les sources actuelles
        current = db.query(ScrapingSource).all()
        print(f"\n{'='*60}")
        print(f"SOURCES ACTUELLES ({len(current)})")
        print(f"{'='*60}")
        for s in current:
            print(f"  [{s.id}] {s.nom} → {s.url}")
            print(f"       actif={s.actif} | last_scraped={s.last_scraped}")

        # 2. Désactiver les sources qui retournent 404 ou DNS error
        disabled = 0
        for s in current:
            url = (s.url or "").lower()
            is_fake = any([
                "secteur-medicale" in url,
                "medical-equipment" in url,
                "medical-marketplace" in url,
                # Ajoutez d'autres patterns faux ici
            ])
            if is_fake and s.actif:
                s.actif = False
                disabled += 1
                print(f"  ❌ Désactivée : {s.nom} ({s.url})")

        print(f"\n{disabled} source(s) désactivée(s)")

        # 3. Ajouter les vraies sources (si pas déjà présentes)
        added = 0
        for source_data in REAL_SOURCES:
            exists = (
                db.query(ScrapingSource)
                .filter_by(url=source_data["url"])
                .first()
            )
            if not exists:
                new_source = ScrapingSource(
                    nom=source_data["nom"],
                    url=source_data["url"],
                    type=source_data["type"],
                    actif=True,
                    max_pages=3,
                    use_browser=False,
                )
                db.add(new_source)
                added += 1
                print(f"  ✅ Ajoutée : {source_data['nom']}")

        print(f"\n{added} source(s) ajoutée(s)")

        # 4. Résumé final
        total_active = (
            db.query(ScrapingSource)
            .filter_by(actif=True)
            .count()
        )
        print(f"\nTotal sources actives : {total_active}")


if __name__ == "__main__":
    fix_sources()