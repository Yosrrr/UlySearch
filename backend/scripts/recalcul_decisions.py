r"""
Recalcule les décisions de CompanyTender avec les règles actuelles (sans IA).

SIMULATION par défaut.     python scripts\recalcul_decisions.py
Un seul client :           python scripts\recalcul_decisions.py --company 6
Appliquer :                python scripts\recalcul_decisions.py --apply

Protections :
- ne touche pas aux offres traitées (statut != 'nouveau') ni à celles avec un avis client ;
- ne supprime rien : l'ancienne décision est gardée dans score_details['_recalcul'] ;
- sauvegarde JSON avant écriture ; aucun appel IA ; aucun email.
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.models.commercial import Commercial
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.sotradies import Sotradies
from app.services.keyword_classifier import score_all_categories


def _best(details):
    best_cat, best_score = None, 0
    for cat, d in (details or {}).items():
        try:
            s = int((d or {}).get("score", 0) or 0)
        except (TypeError, ValueError):
            s = 0
        if s > best_score:
            best_cat, best_score = cat, s
    return best_cat, best_score


def _commercial_name(cat, rules, categories):
    rule = (rules or {}).get(cat)
    if isinstance(rule, str) and rule.strip():
        return rule.strip()
    if isinstance(rule, (list, tuple)):
        for r in rule:
            if r and str(r).strip():
                return str(r).strip()
    if isinstance(rule, dict):
        v = rule.get("commercial") or rule.get("nom")
        if v:
            return str(v).strip()
    c = (categories or {}).get(cat) or {}
    if isinstance(c, dict) and c.get("commercial"):
        return str(c["commercial"]).strip()
    return None


def main(apply: bool, company_filter: int | None) -> None:
    db = SessionLocal()
    stats, examples, backup = Counter(), [], []
    try:
        configs = {
            c.company_id: c
            for c in db.query(Configuration).filter(Configuration.company_id.isnot(None))
        }
        commerciaux = {
            (c.company_id, c.nom): c.id
            for c in db.query(Commercial).filter(Commercial.actif.is_(True))
        }

        q = db.query(CompanyTender, Sotradies).join(
            Sotradies, Sotradies.id == CompanyTender.tender_id
        )
        if company_filter is not None:
            q = q.filter(CompanyTender.company_id == company_filter)

        for ct, t in q.all():
            cfg = configs.get(ct.company_id)
            if cfg is None or not cfg.categories:
                stats["ignoré : pas de configuration"] += 1
                continue
            if (ct.statut or "nouveau") != "nouveau" or ct.feedback:
                stats["protégé : déjà traité ou avis client"] += 1
                continue

            details = score_all_categories(t, cfg.categories, cfg.exclusion_keywords or [])
            cat, score = _best(details)
            new = "retenu" if score >= cfg.score_decision_threshold else "rejete"

            if new == ct.decision and (new == "rejete" or (score == ct.score and cat == ct.categorie)):
                stats["inchangé"] += 1
                continue

            key = f"{ct.decision} -> {new}"
            stats[key] += 1

            new_commercial_id = ct.commercial_id
            if new == "retenu":
                name = _commercial_name(cat, cfg.assignment_rules, cfg.categories)
                new_commercial_id = commerciaux.get((ct.company_id, name))
                if new_commercial_id is None:
                    stats["⚠ retenu sans commercial trouvé"] += 1

            if len(examples) < 20:
                examples.append(
                    f"  [c{ct.company_id}] {key:<17} {ct.score:>3}->{score:<3} "
                    f"{cat or '-'} | {(t.objet or '')[:70]}"
                )

            if apply:
                backup.append({
                    "id": ct.id, "decision": ct.decision, "score": ct.score,
                    "categorie": ct.categorie, "commercial_id": ct.commercial_id,
                    "score_details": ct.score_details,
                })
                details["_recalcul"] = {
                    "date": datetime.now().isoformat(timespec="seconds"),
                    "methode": "regles_v2",
                    "ancienne_decision": ct.decision,
                    "ancien_score": ct.score,
                    "ancienne_categorie": ct.categorie,
                }
                ct.decision = new
                ct.score = score
                ct.categorie = cat
                ct.commercial_id = new_commercial_id
                ct.score_details = details
                flag_modified(ct, "score_details")

        print("=== Résumé ===")
        for k, v in sorted(stats.items()):
            print(f"  {k:<40} {v}")
        print("\n=== Exemples de changements ===")
        print("\n".join(examples) or "  (aucun)")

        if apply:
            path = Path(__file__).with_name(
                f"_backup_recalcul_{datetime.now():%Y%m%d_%H%M%S}.json")
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
            db.commit()
            print(f"\nÉcrit en base ({len(backup)} lignes). Sauvegarde : {path}")
        else:
            db.rollback()
            print("\nSIMULATION : rien n'a été écrit.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    company = None
    if "--company" in sys.argv:
        company = int(sys.argv[sys.argv.index("--company") + 1])
    main(apply="--apply" in sys.argv, company_filter=company)