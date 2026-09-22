from copy import deepcopy
from sqlalchemy.orm.attributes import flag_modified

from app.models import commercial, company, configuration, user  # noqa: F401
from app.core.database import session_scope
from app.services.config_service import get_or_create_config

with session_scope() as db:
    config = get_or_create_config(db)

    # Exclusions
    exclusions = [
        kw for kw in (config.exclusion_keywords or [])
        if kw not in ("conseiljuridique", "terme hors secteur")
    ]
    if "conseil juridique" not in exclusions:
        exclusions.append("conseil juridique")

    # Mots-clés matériel roulant
    categories = deepcopy(config.categories or {})
    roulant = categories.get("MATERIEL_ROULANT", {})
    kws = list(roulant.get("keywords", []))
    for kw in ("moyen de transport", "moyens de transport",
               "vehicule de transport", "véhicule de transport"):
        if kw not in kws:
            kws.append(kw)
    roulant["keywords"] = kws
    categories["MATERIEL_ROULANT"] = roulant

    config.exclusion_keywords = exclusions
    config.categories = categories
    flag_modified(config, "exclusion_keywords")
    flag_modified(config, "categories")

    print("Exclusions :", exclusions)
    print("MATERIEL_ROULANT :", kws)
