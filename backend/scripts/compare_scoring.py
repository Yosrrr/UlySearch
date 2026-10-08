"""
Compare (LECTURE SEULE) la décision enregistrée et celle du nouveau
classificateur (règles uniquement, sans IA). N'écrit rien en base.

Usage : python scripts\compare_scoring.py
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
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


def _was_ai(score_details):
    return any(
        isinstance(d, dict) and d.get("methode") == "ia"
        for d in (score_details or {}).values()
    )


def main(max_examples=10):
    db = SessionLocal()
    try:
        configs = {
            c.company_id: c
            for c in db.query(Configuration)
            .filter(Configuration.company_id.isnot(None))
            .all()
        }
        rows = (
            db.query(CompanyTender, Sotradies)
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .all()
        )

        stats = Counter()
        per_company = defaultdict(Counter)
        gagnes, perdus = [], []

        for ct, t in rows:
            cfg = configs.get(ct.company_id)
            if cfg is None or not cfg.categories:
                stats["sans_configuration"] += 1
                continue

            details = score_all_categories(
                t, cfg.categories, cfg.exclusion_keywords or []
            )
            cat, score = _best(details)
            new = "retenu" if score >= cfg.score_decision_threshold else "rejete"
            key = f"{ct.decision} -> {new}"
            stats[key] += 1
            per_company[ct.company_id][key] += 1

            if ct.decision == "rejete" and new == "retenu":
                matches = (details.get(cat) or {}).get("mots_cles_matches")
                gagnes.append((ct.company_id, score, cat, matches, t.objet))
            elif ct.decision == "retenu" and new == "rejete":
                origine = "IA" if _was_ai(ct.score_details) else "règles"
                perdus.append((ct.company_id, ct.score, ct.categorie, origine, t.objet))

        print("=== Résumé global ===")
        for k, v in sorted(stats.items()):
            print(f"  {k:<22} {v}")

        print("\n=== Par entreprise ===")
        for cid, c in sorted(per_company.items()):
            print(f"  company {cid}: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))

        print(f"\n=== Nouvellement RETENUES ({len(gagnes)}) — à vérifier : vraies opportunités ? ===")
        for cid, score, cat, m, objet in gagnes[:max_examples]:
            print(f"  [c{cid}] {score:>3} {cat} {m} | {(objet or '')[:90]}")

        print(f"\n=== Plus retenues ({len(perdus)}) — à vérifier : vraies pertes ? ===")
        for cid, score, cat, origine, objet in perdus[:max_examples]:
            print(f"  [c{cid}] ancien={score:>3} {cat} (via {origine}) | {(objet or '')[:90]}")
    finally:
        db.rollback()   # garantie : aucune écriture
        db.close()


if __name__ == "__main__":
    main()