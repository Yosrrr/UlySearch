"""Correction de la configuration métier."""

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

        # 1. CHAFARDAGE -> CHAUFFAGE
        old_heating = categories.pop("CHAFARDAGE", None)

        if old_heating:
            if "CHAUFFAGE" not in categories:
                categories["CHAUFFAGE"] = old_heating

            old_rule = rules.pop("CHAFARDAGE", None)

            if old_rule and "CHAUFFAGE" not in rules:
                rules["CHAUFFAGE"] = old_rule

        # 2. CENTRALES_SOLAIRES : mots spécifiques
        if "CENTRALES_SOLAIRES" in categories:
            categories["CENTRALES_SOLAIRES"]["keywords"] = [
                "centrale solaire",
                "centrale photovoltaique",
                "centrale photovoltaïque",
                "parc solaire",
                "parc photovoltaique",
                "parc photovoltaïque",
                "production energie solaire",
                "production énergie solaire",
                "construction centrale solaire",
                "installation centrale photovoltaique",
                "installation centrale photovoltaïque",
            ]

        # 3. MOBILIER_SCOLAIRE
        if "MOBILIER_SCOLAIRE" in categories:
            categories["MOBILIER_SCOLAIRE"]["keywords"] = [
                "mobilier scolaire",
                "table scolaire",
                "tables scolaires",
                "chaise scolaire",
                "chaises scolaires",
                "bureau eleve",
                "bureau élève",
                "equipement scolaire",
                "équipement scolaire",
                "tables pour ecoles",
                "chaises pour ecoles",
            ]

        # 4. MOBILIER_PROFESSIONNEL
        if "MOBILIER_PROFESSIONNEL" in categories:
            categories["MOBILIER_PROFESSIONNEL"]["keywords"] = [
                "mobilier de bureau",
                "fauteuil de bureau",
                "fauteuils de bureau",
                "bureau administratif",
                "bureaux administratifs",
                "armoire de bureau",
                "armoires de bureau",
                "table de reunion",
                "table de réunion",
            ]

        # 5. Exclusions supplémentaires
        additional_exclusions = [
            "denrees alimentaires",
            "denrées alimentaires",
            "restauration collective",
            "cabinet avocat",
            "cabinet d'avocats",
            "conseil juridique",
        ]

        for keyword in additional_exclusions:
            if keyword not in exclusions:
                exclusions.append(keyword)

        # Nettoyer les anciennes valeurs cassées avec des ?
        cleaned_categories = {}

        for cat_id, cat_data in categories.items():
            if not isinstance(cat_data, dict):
                cleaned_categories[cat_id] = cat_data
                continue

            cleaned = dict(cat_data)

            cleaned["keywords"] = [
                keyword
                for keyword in cat_data.get("keywords", [])
                if "?" not in keyword
            ]

            cleaned["marques"] = [
                brand
                for brand in cat_data.get("marques", [])
                if "?" not in brand
            ]

            cleaned_categories[cat_id] = cleaned

        cleaned_exclusions = [
            keyword
            for keyword in exclusions
            if "?" not in keyword
        ]

        config.categories = cleaned_categories
        config.assignment_rules = rules
        config.exclusion_keywords = cleaned_exclusions

        flag_modified(config, "categories")
        flag_modified(config, "assignment_rules")
        flag_modified(config, "exclusion_keywords")

        print("Configuration nettoyée et corrigée.")
        print()

        for cat_id in [
            "CENTRALES_SOLAIRES",
            "CHAUFFAGE",
            "MOBILIER_SCOLAIRE",
            "MOBILIER_PROFESSIONNEL",
        ]:
            cat = cleaned_categories.get(cat_id)

            if cat:
                print(f"{cat_id} :")

                for keyword in cat.get("keywords", []):
                    print(f"  - {keyword}")

                print()

        print(
            "Exclusions :",
            cleaned_exclusions,
        )


if __name__ == "__main__":
    main()