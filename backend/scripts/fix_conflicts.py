"""Résolution des conflits entre catégories."""

from copy import deepcopy

from sqlalchemy.orm.attributes import flag_modified

from app.models import (  # noqa: F401
    commercial,
    company,
    configuration,
    user,
)

from app.core.database import session_scope
from app.services.config_service import get_or_create_config


def main() -> None:
    with session_scope() as db:
        config = get_or_create_config(db)

        categories = deepcopy(config.categories or {})
        rules = deepcopy(config.assignment_rules or {})
        exclusions = list(config.exclusion_keywords or [])

        # ---------------------------------------------------
        # 1. Résolution MATMONT / ENGINS_TP
        #
        # Décision : ENGINS_TP garde chargeuse + tractopelle.
        # MATMONT est supprimée.
        # ---------------------------------------------------

        if "MATMONT" in categories:
            del categories["MATMONT"]

        if "MATMONT" in rules:
            del rules["MATMONT"]

        # ---------------------------------------------------
        # 2. Résolution VEHICULESINDUSTRIELS
        #
        # chariot élévateur → MANUTENTION (déjà présent)
        # compacteur        → ENGINS_TP (déjà présent)
        # → suppression de VEHICULESINDUSTRIELS
        # ---------------------------------------------------

        if "VEHICULESINDUSTRIELS" in categories:
            del categories["VEHICULESINDUSTRIELS"]

        if "VEHICULESINDUSTRIELS" in rules:
            del rules["VEHICULESINDUSTRIELS"]

        # ---------------------------------------------------
        # 3. ENGINS_SPECIAUX sans commercial
        #
        # Décision : supprimé.
        # Vous pourrez le recréer plus tard avec un commercial.
        # ---------------------------------------------------

        if "ENGINS_SPECIAUX" in categories:
            del categories["ENGINS_SPECIAUX"]

        # ---------------------------------------------------
        # 4. GROUPES_ELECTROGENES : assigner un commercial
        #
        # Modifiez la valeur ci-dessous selon votre organisation.
        # Mettre None pour laisser sans commercial.
        # ---------------------------------------------------

        target_commercial_groupes = "Ramzi Trabelsi"

        if "GROUPES_ELECTROGENES" in categories:
            categories["GROUPES_ELECTROGENES"]["commercial"] = (
                target_commercial_groupes
            )

            if target_commercial_groupes:
                rules["GROUPES_ELECTROGENES"] = [
                    target_commercial_groupes
                ]

        # ---------------------------------------------------
        # 5. Nettoyer les exclusions
        # ---------------------------------------------------

        fixed_exclusions = []

        for keyword in exclusions:
            if not isinstance(keyword, str):
                continue

            cleaned = keyword.strip()

            # Corriger "conseiljuridique"
            if cleaned == "conseiljuridique":
                cleaned = "conseil juridique"

            if not cleaned:
                continue

            if "?" in cleaned:
                continue

            if cleaned in fixed_exclusions:
                continue

            fixed_exclusions.append(cleaned)

        config.categories = categories
        config.assignment_rules = rules
        config.exclusion_keywords = fixed_exclusions

        flag_modified(config, "categories")
        flag_modified(config, "assignment_rules")
        flag_modified(config, "exclusion_keywords")

        print("Conflits résolus.")
        print()
        print(f"Catégories : {len(categories)}")
        print(f"Règles     : {rules}")
        print(f"Exclusions : {fixed_exclusions}")


if __name__ == "__main__":
    main()