"""
Recalcule score, catégorie, commercial et statut de tous les marchés
avec la configuration actuelle.

    python -m scripts.rescore_tenders           # prévisualisation
    python -m scripts.rescore_tenders --apply   # application
"""
import sys
from datetime import UTC, datetime

from app.models import commercial, company, configuration, user  # noqa: F401
from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.schemas.sotradies import SotradiesRaw
from app.services.config_service import get_or_create_config
from app.services.scoring_orchestrator import score_tender_full
from app.services.pipeline import _best_category, _resolve_commercial

# Statuts fixés manuellement par un utilisateur : ne jamais les écraser.
PROTECTED_STATUSES = {"sans_suite"}


def main() -> None:
    apply = "--apply" in sys.argv

    with session_scope() as db:
        config = get_or_create_config(db)
        categories = config.categories or {}
        exclusions = config.exclusion_keywords or []
        rules = config.assignment_rules or {}
        seuil = config.score_decision_threshold

        tenders = db.query(Sotradies).all()
        changed = 0

        for t in tenders:
            raw = SotradiesRaw(
                source=t.source,
                reference=t.reference,
                objet=t.objet,
                acheteur=t.acheteur or "Non précisé",
                categorie=None,
                date_publication=t.date_publication,
                date_limite=t.date_limite,
                budget_estime=float(t.budget_estime) if t.budget_estime else None,
                lien=t.lien,
            )

            details = score_tender_full(raw, categories, exclusions) or {}
            cat, score = _best_category(details)
            com = _resolve_commercial(cat, rules, categories)

            if t.statut in PROTECTED_STATUSES:
                new_status = t.statut
            else:
                new_status = "retenu" if score >= seuil else "nouveau"

            old = (t.categorie, t.commercial_assigne, t.statut)
            new = (cat, com, new_status)

            if old != new:
                changed += 1
                print(f"[{t.objet[:55]}]")
                print(f"    {old}  ->  {new}  (score={score}%)")

                if apply:
                    t.score_details = details
                    t.categorie = cat
                    t.commercial_assigne = com
                    t.statut = new_status
                    t.date_derniere_action = datetime.now(UTC).replace(tzinfo=None)

        print()
        print(f"{changed}/{len(tenders)} marche(s) modifie(s)"
              + ("" if apply else " — PREVISUALISATION, relancez avec --apply"))


if __name__ == "__main__":
    main()