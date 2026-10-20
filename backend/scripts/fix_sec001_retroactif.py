"""SEC-001 rétroactif : désactive les sources jamais approuvées par la plateforme.

Avant le correctif SEC-001, les sources proposées à l'inscription étaient
activées automatiquement. Ce script les repasse en inactif pour qu'un
superadmin les réexamine. Les sources officielles (ONMP, TUNEPS) sont
préservées.

Usage :
  python -m scripts.fix_sec001_retroactif            # dry-run (liste seulement)
  python -m scripts.fix_sec001_retroactif --apply    # applique
"""
import sys

from app.core.database import session_scope
from app.models.scraping_source import ScrapingSource

# Sources officielles gérées par la plateforme : ne pas toucher
SOURCES_PLATEFORME = {"onmp", "tuneps"}


def main() -> None:
    apply = "--apply" in sys.argv
    with session_scope() as db:
        candidates = (
            db.query(ScrapingSource)
            .filter(ScrapingSource.actif.is_(True))
            .filter(ScrapingSource.type == "universel")
            .all()
        )
        a_desactiver = [
            s for s in candidates
            if (s.nom or "").lower() not in SOURCES_PLATEFORME
        ]
        if not a_desactiver:
            print("Aucune source a desactiver.")
            return

        print(f"{len(a_desactiver)} source(s) concernee(s) :")
        for s in a_desactiver:
            print(f"  id={s.id}  nom={s.nom!r}  url={s.url}")

        if apply:
            for s in a_desactiver:
                s.actif = False
            db.commit()
            print("\nAppliquee : sources desactivees. Reactivation via superadmin.")
        else:
            print("\nDRY-RUN : relancer avec --apply pour appliquer.")


if __name__ == "__main__":
    main()