"""
Recalcule acheteur_connu sur les marchés déjà présents en base.
Utilisé automatiquement après create/update/import de known_buyers.
"""

from app.core.database import session_scope
from app.models.known_buyer import KnownBuyer
from app.models.sotradies import Sotradies
from app.services.buyer_matcher import find_matching_buyer


def rematch_all_tenders() -> int:
    with session_scope() as db:
        known_buyers = db.query(KnownBuyer).all()
        tenders = db.query(Sotradies).all()

        updated = 0

        for tender in tenders:
            best_kb = find_matching_buyer(tender.acheteur, known_buyers)
            new_value = best_kb.client_sotradies if best_kb else None

            if tender.acheteur_connu != new_value:
                tender.acheteur_connu = new_value
                updated += 1

        print(f"[buyer_rematcher] Marchés rematchés : {updated}")
        return updated
    