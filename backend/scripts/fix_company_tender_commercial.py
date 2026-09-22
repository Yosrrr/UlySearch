"""Corrige les CompanyTender.commercial_id manquants."""
import app.models  # noqa: F401
from app.core.database import session_scope
from app.models.company_tender import CompanyTender
from app.models.sotradies import Sotradies
from app.models.commercial import Commercial


def main() -> None:
    with session_scope() as db:
        matches = (
            db.query(CompanyTender)
            .filter(
                CompanyTender.commercial_id.is_(None),
                CompanyTender.decision == "retenu",
            )
            .all()
        )
        print(f"CompanyTender retenus sans commercial : {len(matches)}")

        fixed = 0
        for match in matches:
            tender = db.query(Sotradies).filter_by(id=match.tender_id).first()
            if not tender or not tender.commercial_assigne:
                print(f"  IGNORE (pas de commercial_assigne) : {match.tender_id}")
                continue

            commercial = (
                db.query(Commercial)
                .filter(
                    Commercial.company_id == match.company_id,
                    Commercial.nom == tender.commercial_assigne,
                )
                .first()
            )

            if commercial:
                match.commercial_id = commercial.id
                fixed += 1
                print(f"  OK  : {tender.objet[:50]!r} -> {commercial.nom}")
            else:
                print(
                    f"  MANQUANT : {tender.objet[:50]!r} -> "
                    f"{tender.commercial_assigne!r} introuvable pour company_id={match.company_id}"
                )

        print(f"\n{fixed} CompanyTender corrige(s)")


if __name__ == "__main__":
    main()