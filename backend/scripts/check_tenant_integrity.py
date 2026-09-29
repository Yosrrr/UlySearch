"""Diagnostic de cohérence multi-client, en lecture seule."""

from sqlalchemy import text

from app.core.database import session_scope


TENANT_TABLES = (
    "configuration",
    "commercials",
    "known_buyers",
    "company_sources",
    "company_tenders",
)


def main() -> int:
    errors = 0

    with session_scope() as db:
        # Première instruction de la transaction.
        db.execute(text("SET TRANSACTION READ ONLY"))

        database = db.execute(
            text("SELECT current_database()")
        ).scalar_one()

        print(f"Base controlee : {database}")

        companies = db.execute(
            text("SELECT id, nom FROM companies ORDER BY id")
        ).all()

        print(f"Entreprises presentes : {len(companies)}")

        for company in companies:
            print(f"  [{company.id}] {company.nom}")

        checks = [
            (
                "Utilisateurs clients sans entreprise valide",
                """
                SELECT COUNT(*)
                FROM users u
                LEFT JOIN companies c ON c.id = u.company_id
                WHERE u.profil <> 'superadmin'
                  AND (u.company_id IS NULL OR c.id IS NULL)
                """,
            ),
            (
                "Assignations vers un commercial d'une autre entreprise",
                """
                SELECT COUNT(*)
                FROM company_tenders ct
                LEFT JOIN commercials c ON c.id = ct.commercial_id
                WHERE ct.commercial_id IS NOT NULL
                  AND (
                    c.id IS NULL
                    OR c.company_id IS DISTINCT FROM ct.company_id
                  )
                """,
            ),
            (
                "Doublons entreprise/marche",
                """
                SELECT COUNT(*)
                FROM (
                    SELECT company_id, tender_id
                    FROM company_tenders
                    GROUP BY company_id, tender_id
                    HAVING COUNT(*) > 1
                ) duplicates
                """,
            ),
            (
                "Plusieurs configurations pour une entreprise",
                """
                SELECT COUNT(*)
                FROM (
                    SELECT company_id
                    FROM configuration
                    WHERE company_id IS NOT NULL
                    GROUP BY company_id
                    HAVING COUNT(*) > 1
                ) duplicates
                """,
            ),
        ]

        # Les noms des tables viennent uniquement de la liste fixe ci-dessus.
        for table_name in TENANT_TABLES:
            checks.append((
                f"{table_name} : lignes sans entreprise valide",
                f"""
                SELECT COUNT(*)
                FROM {table_name} t
                LEFT JOIN companies c ON c.id = t.company_id
                WHERE t.company_id IS NULL OR c.id IS NULL
                """,
            ))

        print()

        for label, statement in checks:
            count = db.execute(text(statement)).scalar_one()
            status = "OK" if count == 0 else "ECHEC"

            print(f"[{status}] {label} : {count}")

            if count:
                errors += 1

    print()
    print(
        "Ce diagnostic controle les donnees, "
        "pas les autorisations des API."
    )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())