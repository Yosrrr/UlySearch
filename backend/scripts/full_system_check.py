"""
Test complet du système multi-tenant Sotradies.

Vérifie, dans l'ordre :
1. Import de tous les modèles et résolution des mappers SQLAlchemy.
2. Cohérence de la base (tables, colonnes attendues).
3. État des données (companies, users, commercials, configuration).
4. Isolation multi-tenant (aucune donnée orpheline).
5. Cohérence des CompanyTender (commercial_id, decision).
6. Import complet de l'application FastAPI.

Ne modifie AUCUNE donnée. Usage :
    python -m scripts.full_system_check
"""
import sys
from sqlalchemy import text
import app.models  
from sqlalchemy.orm import configure_mappers
from sqlalchemy import inspect

from app.core.database import engine, session_scope
from app.models.company import Company
from app.models.company_source import CompanySource
from app.models.company_tender import CompanyTender
from app.models.commercial import Commercial
from app.models.configuration import Configuration
from app.models.scraping_source import ScrapingSource
from app.models.source_account import SourceAccount
from app.models.sotradies import Sotradies
from app.models.user import User

ERRORS: list[str] = []
WARNINGS: list[str] = []


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def check(label: str, condition: bool, error_msg: str = "", warning: bool = False) -> None:
    status = "OK" if condition else ("WARN" if warning else "FAIL")
    print(f"  [{status}] {label}")
    if not condition:
        (WARNINGS if warning else ERRORS).append(f"{label} — {error_msg}")


def main() -> None:
    # ------------------------------------------------------------------
    section("1. MAPPERS SQLALCHEMY")
    # ------------------------------------------------------------------
    try:
        configure_mappers()
        check("Tous les mappers se résolvent sans erreur", True)
    except Exception as exc:
        check("Résolution des mappers", False, str(exc))

    # ------------------------------------------------------------------
    section("2. STRUCTURE DE LA BASE")
    # ------------------------------------------------------------------
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    required_tables = {
        "users", "companies", "commercials", "configuration",
        "scraping_sources", "sotradies", "company_sources",
        "company_tenders", "sent_log", "source_accounts",
    }
    for table in sorted(required_tables):
        check(f"Table '{table}' existe", table in tables,
              "table manquante — migration non appliquée ?")

    if "users" in tables:
        cols = {c["name"] for c in insp.get_columns("users")}
        check("users.company_id existe", "company_id" in cols)

    if "companies" in tables:
        cols = {c["name"]: c["nullable"] for c in insp.get_columns("companies")}
        check("companies.owner_id existe", "owner_id" in cols)
        check("companies.owner_id est nullable", cols.get("owner_id") is True,
              "owner_id doit être nullable pour permettre la création")

    if "configuration" in tables:
        cols = {c["name"] for c in insp.get_columns("configuration")}
        check("configuration.company_id existe", "company_id" in cols)

    if "commercials" in tables:
        cols = {c["name"] for c in insp.get_columns("commercials")}
        check("commercials.company_id existe", "company_id" in cols)

    if "sent_log" in tables:
        cols = {c["name"] for c in insp.get_columns("sent_log")}
        check(
            "sent_log.company_tender_id existe",
            "company_tender_id" in cols,
            "migration SentLog non appliquée",
            warning=True,
        )

    # ------------------------------------------------------------------
    section("3. ÉTAT DES DONNÉES")
    # ------------------------------------------------------------------
    with session_scope() as db:
        n_companies = db.query(Company).count()
        n_users = db.query(User).count()
        n_commercials = db.query(Commercial).count()
        n_configs = db.query(Configuration).count()
        n_sources = db.query(ScrapingSource).count()
        n_tenders = db.query(Sotradies).count()
        n_company_sources = db.query(CompanySource).count()
        n_source_accounts = db.query(SourceAccount).count()
        n_company_tenders = db.query(CompanyTender).count()

        print(f"  Companies         : {n_companies}")
        print(f"  Users             : {n_users}")
        print(f"  Commercials       : {n_commercials}")
        print(f"  Configurations    : {n_configs}")
        print(f"  ScrapingSources   : {n_sources}")
        print(f"  Sotradies (offres): {n_tenders}")
        print(f"  CompanySources    : {n_company_sources}")
        print(f"  SourceAccounts    : {n_source_accounts}")
        print(f"  CompanyTenders    : {n_company_tenders}")

        check("Au moins une Company existe", n_companies >= 1,
              "aucune entreprise — lancer backfill_company.py")
        check("Au moins une Configuration existe", n_configs >= 1)
        check("Au moins un Commercial existe", n_commercials >= 1)

        # ------------------------------------------------------------------
        section("4. ISOLATION MULTI-TENANT (données orphelines)")
        # ------------------------------------------------------------------
        orphan_users = db.query(User).filter(
            User.company_id.is_(None), User.profil != "superadmin"
        ).count()
        check(
            "Aucun user non-superadmin sans company_id",
            orphan_users == 0,
            f"{orphan_users} utilisateur(s) orphelin(s)",
            warning=True,
        )

        orphan_configs = db.query(Configuration).filter(
            Configuration.company_id.is_(None)
        ).count()
        check(
            "Aucune configuration orpheline",
            orphan_configs == 0,
            f"{orphan_configs} configuration(s) orpheline(s) (V1 résiduelle)",
            warning=True,
        )

        orphan_commercials = db.query(Commercial).filter(
            Commercial.company_id.is_(None)
        ).count()
        check(
            "Aucun commercial orphelin",
            orphan_commercials == 0,
            f"{orphan_commercials} commercial(aux) orphelin(s)",
            warning=True,
        )

        # ------------------------------------------------------------------
        section("5. COHÉRENCE COMPANY_TENDER")
        # ------------------------------------------------------------------
        n_retenus = db.query(CompanyTender).filter_by(decision="retenu").count()
        n_retenus_sans_commercial = (
            db.query(CompanyTender)
            .filter(CompanyTender.decision == "retenu", CompanyTender.commercial_id.is_(None))
            .count()
        )
        print(f"  CompanyTender retenus            : {n_retenus}")
        print(f"  ... dont sans commercial assigné : {n_retenus_sans_commercial}")

        check(
            "Tous les retenus ont un commercial",
            n_retenus_sans_commercial == 0,
            f"{n_retenus_sans_commercial} marché(s) retenu(s) sans commercial",
            warning=True,
        )

        # Vérifier qu'aucun commercial n'est assigné à un CompanyTender
        # d'une autre entreprise (violation d'isolation critique).
        cross_tenant = (
            db.query(CompanyTender, Commercial)
            .join(Commercial, Commercial.id == CompanyTender.commercial_id)
            .filter(Commercial.company_id != CompanyTender.company_id)
            .count()
        )
        check(
            "Aucune fuite cross-tenant (commercial d'une autre société)",
            cross_tenant == 0,
            f"{cross_tenant} violation(s) d'isolation détectée(s) !",
        )

        # Vérifier l'unicité (company_id, tender_id)
        duplicates = db.execute(text("""
            SELECT company_id, tender_id, COUNT(*)
            FROM company_tenders
            GROUP BY company_id, tender_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        check(
            "Aucun doublon (company_id, tender_id)",
            len(duplicates) == 0,
            f"{len(duplicates)} doublon(s) trouvé(s)",
        )

    # ------------------------------------------------------------------
    section("6. IMPORT DE L'APPLICATION")
    # ------------------------------------------------------------------
    try:
        import app.main  # noqa: F401
        check("app.main s'importe sans erreur", True)
    except Exception as exc:
        check("Import app.main", False, str(exc))

    # ------------------------------------------------------------------
    section("RÉSUMÉ FINAL")
    # ------------------------------------------------------------------
    if WARNINGS:
        print(f"\n⚠️  {len(WARNINGS)} avertissement(s) :")
        for w in WARNINGS:
            print(f"   - {w}")

    if ERRORS:
        print(f"\n❌ {len(ERRORS)} ERREUR(S) BLOQUANTE(S) :")
        for e in ERRORS:
            print(f"   - {e}")
        print("\n❌ SYSTÈME NON VALIDE — corriger avant de continuer.")
        sys.exit(1)
    else:
        print("\n✅ SYSTÈME VALIDE — aucune erreur bloquante.")
        if WARNINGS:
            print("   (des avertissements existent, à examiner)")


if __name__ == "__main__":
    main()