"""
Recalcule acheteur_connu sur les marchés par entreprise.
Chaque entreprise ne voit que SES buyers dans SES company_tenders.

F-027 : ne plus écrire dans la table globale sotradies.
"""

from app.core.database import session_scope
from app.models.company_tender import CompanyTender
from app.models.known_buyer import KnownBuyer
from app.models.sotradies import Sotradies
from app.services.buyer_matcher import find_matching_buyer
from sqlalchemy import or_
from app.models.configuration import Configuration

def rematch_company_tenders(company_id: int) -> int:
    """Rematch les marchés d'UNE entreprise avec SES acheteurs uniquement."""
    if company_id is None:
        return 0

    with session_scope() as db:
        known_buyers = (
            db.query(KnownBuyer)
            .filter(KnownBuyer.company_id == company_id)
            .all()
        )

        if not known_buyers:
            return 0

        matches = (
            db.query(CompanyTender, Sotradies)
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(CompanyTender.company_id == company_id)
            .all()
        )

        updated = 0
        for ct, tender in matches:
            best_kb = find_matching_buyer(tender.acheteur, known_buyers)
            new_value = best_kb.client_sotradies if best_kb else "Inconnu"

            if ct.acheteur_connu != new_value:
                ct.acheteur_connu = new_value
                updated += 1

        print(f"[buyer_rematcher] Company {company_id} : {updated} marché(s) rematché(s)")
        return updated


def rematch_all_tenders() -> int:
    """Rematch pour toutes les entreprises, isolé par tenant."""
    from app.models.configuration import Configuration

    total = 0
    with session_scope() as db:
        company_ids = [
            c.company_id
            for c in db.query(Configuration.company_id).all()
        ]

    for cid in company_ids:
        total += rematch_company_tenders(cid)

    print(f"[buyer_rematcher] Total rematchés : {total}")
    return total