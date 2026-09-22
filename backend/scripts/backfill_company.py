"""
Backfill multi-tenant : crée l'entreprise Sotradies
et rattache toutes les données existantes.

    python -m scripts.backfill_company           # prévisualisation
    python -m scripts.backfill_company --apply   # application
"""

import sys
from datetime import datetime

from app.models import (  # noqa: F401
    audit_log, commercial, company, company_source,
    company_tender, configuration, scraping_source,
    sent_log, sotradies, user,
)
from app.core.database import session_scope
from app.models.company import Company
from app.models.commercial import Commercial as CommercialModel
from app.models.company_source import CompanySource
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.scraping_source import ScrapingSource
from app.models.sotradies import Sotradies
from app.models.user import User

APPLY = "--apply" in sys.argv


def main() -> None:
    separator = "=" * 60

    print(separator)
    print(
        "BACKFILL MULTI-TENANT",
        "(APPLICATION RÉELLE)" if APPLY else "(PRÉVISUALISATION)",
    )
    print(separator)

    with session_scope() as db:

        # ── 1. Créer la Company Sotradies ──────────────────────
        existing_company = (
            db.query(Company)
            .filter(Company.nom == "Sotradies")
            .first()
        )

        if existing_company:
            company_id = existing_company.id
            print(f"Company Sotradies déjà présente (id={company_id})")
        elif not APPLY:
            print("PREVIEW : Company 'Sotradies' serait créée")
            company_id = -1
        else:
            new_company = Company(
                nom="Sotradies",
                pays="Tunisie",
                onboarding_complete=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                # owner_id sera défini après création de la company
            )
            db.add(new_company)
            db.flush()
            company_id = new_company.id
            print(f"✅ Company créée (id={company_id})")

        # ── 2. Trouver le premier admin non-superadmin ──────────
        admin = (
            db.query(User)
            .filter(User.profil.in_(["admin", "user"]))
            .order_by(User.id.asc())
            .first()
        )

        if admin:
            print(
                f"Admin trouvé : {admin.email} "
                f"(profil={admin.profil})"
            )
        else:
            print("⚠️  Aucun admin trouvé — owner_id restera NULL")

        # ── 3. Rattacher les utilisateurs non-superadmin ────────
        all_users = (
            db.query(User)
            .filter(User.profil != "superadmin")
            .all()
        )

        print(f"\nUtilisateurs à rattacher : {len(all_users)}")

        for u in all_users:
            print(f"  - {u.email} ({u.profil})")

            if APPLY:
                u.company_id = company_id

        # Définir owner après avoir rattaché l'admin
        if APPLY and admin and company_id > 0:
            existing_company_obj = db.get(Company, company_id)

            if existing_company_obj:
                existing_company_obj.owner_id = admin.id
                print(
                    f"\n✅ owner_id défini : {admin.email}"
                )

        # ── 4. Rattacher la configuration globale ───────────────
        global_config = (
            db.query(Configuration)
            .filter(Configuration.company_id.is_(None))
            .first()
        )

        if global_config:
            print(
                f"\nConfiguration globale (id={global_config.id}) "
                "→ rattachée à Sotradies"
            )

            if APPLY:
                global_config.company_id = company_id
        else:
            print("\n⚠️  Aucune configuration globale")

        # ── 5. Rattacher les commerciaux ────────────────────────
        commerciaux = (
            db.query(CommercialModel)
            .filter(CommercialModel.company_id.is_(None))
            .all()
        )

        print(f"\nCommerciaux à rattacher : {len(commerciaux)}")

        for c in commerciaux:
            print(f"  - {c.nom} ({c.email})")

            if APPLY:
                c.company_id = company_id

        # ── 6. Abonnements aux sources ──────────────────────────
        sources = db.query(ScrapingSource).all()

        print(f"\nSources : {len(sources)}")

        for source in sources:
            print(f"  - [{source.id}] {source.nom}")

            if not APPLY:
                continue

            already = (
                db.query(CompanySource)
                .filter_by(
                    company_id=company_id,
                    source_id=source.id,
                )
                .first()
            )

            if not already:
                db.add(CompanySource(
                    company_id=company_id,
                    source_id=source.id,
                    actif=True,
                ))

        # ── 7. Créer les CompanyTenders ─────────────────────────
        tenders = db.query(Sotradies).all()
        print(f"\nMarchés : {len(tenders)}")

        if APPLY:
            created = 0

            for tender in tenders:
                already = (
                    db.query(CompanyTender)
                    .filter_by(
                        company_id=company_id,
                        tender_id=tender.id,
                    )
                    .first()
                )

                if already:
                    continue

                commercial_id = None

                if tender.commercial_assigne:
                    c = (
                        db.query(CommercialModel)
                        .filter_by(
                            company_id=company_id,
                            nom=tender.commercial_assigne,
                        )
                        .first()
                    )

                    if c:
                        commercial_id = c.id

                score = max(
                    (
                        d.get("score", 0)
                        for d in (
                            tender.score_details or {}
                        ).values()
                        if isinstance(d, dict)
                    ),
                    default=0,
                )

                db.add(CompanyTender(
                    company_id=company_id,
                    tender_id=tender.id,
                    score=score,
                    categorie=tender.categorie,
                    score_details=tender.score_details,
                    decision=(
                        "retenu"
                        if tender.statut == "retenu"
                        else "rejete"
                    ),
                    statut="nouveau",
                    commercial_id=commercial_id,
                    acheteur_connu=tender.acheteur_connu,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ))

                created += 1

            print(f"✅ {created} CompanyTender créés")

        if not APPLY:
            print()
            print(separator)
            print("MODE PRÉVISUALISATION — aucune modification")
            print("Relancez avec --apply pour appliquer")
            print(separator)
        else:
            print()
            print(separator)
            print("✅ Backfill terminé")
            print(separator)


if __name__ == "__main__":
    main()