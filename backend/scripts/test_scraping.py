# scripts/test_scoring.py
"""
Test du scoring sur les marchés ONMP existants.
python -m scripts.test_scoring
"""
import sys
sys.path.insert(0, '.')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sys
sys.path.insert(0, '.')

from app.models import (  # noqa: F401
    audit_log, commercial, company, configuration,
    known_buyer, pipeline_log, scraping_source,
    sent_log, sotradies, system_action_log, user,
)

from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.services.config_service import get_or_create_config




from app.core.database import session_scope
from app.models.sotradies import Sotradies
def test_scoring():
    with session_scope() as db:
        config = get_or_create_config(db)

        # 1. Afficher la configuration actuelle
        print("=" * 70)
        print("CONFIGURATION ACTUELLE")
        print("=" * 70)

        categories = config.categories or {}
        print(f"\nCatégories ({len(categories)}) :")
        for cat_id, cat_data in categories.items():
            keywords = cat_data.get("keywords", [])
            marques = cat_data.get("marques", [])
            commercial = cat_data.get("commercial", "NON ASSIGNÉ")
            print(f"\n  {cat_id} :")
            print(f"    Commercial : {commercial}")
            print(f"    Mots-clés  : {keywords[:10]}{'...' if len(keywords) > 10 else ''}")
            print(f"    Marques    : {marques[:5]}{'...' if len(marques) > 5 else ''}")

        exclusions = config.exclusion_keywords or []
        print(f"\nExclusions ({len(exclusions)}) : {exclusions[:10]}")

        seuil = config.score_decision_threshold
        print(f"\nSeuil de rétention : {seuil}%")

        rules = config.assignment_rules or {}
        print(f"\nRègles d'assignation : {rules}")

        # 2. Afficher les marchés en base
        print("\n" + "=" * 70)
        print("MARCHÉS EN BASE")
        print("=" * 70)

        all_markets = (
            db.query(Sotradies)
            .order_by(Sotradies.date_publication.desc())
            .limit(20)
            .all()
        )

        print(f"\nTotal : {db.query(Sotradies).count()} marchés")
        print(f"Retenus : {db.query(Sotradies).filter_by(statut='retenu').count()}")
        print(f"Nouveaux : {db.query(Sotradies).filter_by(statut='nouveau').count()}")

        for m in all_markets:
            score_info = ""
            if m.score_details:
                for cat, detail in m.score_details.items():
                    if isinstance(detail, dict) and detail.get("score", 0) > 0:
                        matched = detail.get("mots_cles_matches", [])
                        methode = detail.get("methode", "?")
                        score_info += f" [{cat}={detail['score']}% ({methode}) mots={matched}]"

            print(
                f"\n  [{m.statut:8s}] {m.source:6s} | "
                f"score={score_info or ' [aucun match]'}"
            )
            print(f"    Objet    : {(m.objet or '')[:70]}")
            print(f"    Acheteur : {m.acheteur or 'N/A'}")
            print(f"    Date pub : {m.date_publication}")
            print(f"    Commerc. : {m.commercial_assigne or 'NON ASSIGNÉ'}")

        # 3. Simuler un marché qui DEVRAIT matcher
        print("\n" + "=" * 70)
        print("SIMULATION : Comment un marché PERTINENT serait scoré")
        print("=" * 70)

        from app.services.scoring_orchestrator import score_tender_full
        from app.schemas.sotradies import SotradiesRaw
        from datetime import datetime

        # Créer un faux marché qui devrait matcher
        test_cases = []

        # Construire des cas de test basés sur les vraies catégories
        for cat_id, cat_data in categories.items():
            keywords = cat_data.get("keywords", [])
            if keywords:
                # Prendre les 2 premiers mots-clés pour construire un titre
                test_title = f"Acquisition de {keywords[0]}"
                if len(keywords) > 1:
                    test_title += f" et {keywords[1]}"
                test_cases.append((cat_id, test_title))

        if not test_cases:
            print("  ⚠️ Aucune catégorie configurée — impossible de simuler")
        else:
            for expected_cat, title in test_cases[:5]:
                fake = SotradiesRaw(
                    source="test",
                    objet=title,
                    acheteur="Ministère Test",
                    categorie="fournitures",
                    date_publication=datetime.now(),
                    reference="TEST-001",
                    date_limite=None,
                    budget_estime=None,
                    lien=None,
                )

                result = score_tender_full(
                    fake,
                    categories,
                    exclusions,
                )

                best_cat, best_score = None, 0
                for cat, detail in (result or {}).items():
                    if isinstance(detail, dict):
                        s = int(detail.get("score", 0) or 0)
                        if s > best_score:
                            best_cat, best_score = cat, s

                status = "✅ RETENU" if best_score >= seuil else "❌ REJETÉ"
                print(f"\n  {status} | score={best_score}% | cat={best_cat}")
                print(f"    Titre simulé : {title}")
                print(f"    Attendu      : {expected_cat}")

                if result:
                    for cat, detail in result.items():
                        if isinstance(detail, dict) and detail.get("score", 0) > 0:
                            print(
                                f"    → {cat} = {detail['score']}% "
                                f"({detail.get('methode', '?')}) "
                                f"mots={detail.get('mots_cles_matches', [])}"
                            )


if __name__ == "__main__":
    test_scoring()