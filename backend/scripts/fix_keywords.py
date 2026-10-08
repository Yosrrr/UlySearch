r"""
Remplace les mots-clés arabes trop généraux (clients 5 et 6).
Par défaut : SIMULATION, rien n'est écrit.
Pour appliquer :  python scripts\fix_keywords.py --apply
"""
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.models.configuration import Configuration

CHANGES = {
    2: {
        "GROUPES_ELECTROGENES": {
            "remove": ["installation electrique"],
            "add": ["groupe electrogene", "مولد كهربائي"],
        },
    },
    6: {
        "ACT_INTEGRA_SOLUTIONS": {
            "remove": ["الصيانة", "الشبكات", "التكامل"],
            "add": ["صيانة الشبكات المعلوماتية", "الشبكات المعلوماتية",
                    "شبكة معلوماتية", "تكامل الأنظمة المعلوماتية"],
        },
        "ACT_AUTOMATISATION": {
            "remove": ["البرامج", "التطبيقات", "السحابة"],
            "add": ["البرمجيات", "برامج معلوماتية",
                    "تطبيقات معلوماتية", "الحوسبة السحابية"],
        },
    },
    5: {
        "SERVICES_INSTALLATION_MAINTENANCE": {
            "remove": [],
            "add": ["تجهيزات طبية", "معدات طبية", "تجهيزات استشفائية"],
        },
    },
    6: {
        "ACT_INTEGRA_SOLUTIONS": {
            "remove": ["réseau"],
            "add": ["réseau informatique", "réseau local", "infrastructure réseau",
                    "câblage informatique"],
        },
        "ACT_DEVELOP_LOGIWEB": {
            "remove": ["refonte"],
            "add": ["refonte du système d'information", "refonte site web",
                    "refonte application"],
        },
    },
}


def main(apply: bool) -> None:
    db = SessionLocal()
    backup = {}
    try:
        for company_id, cats in CHANGES.items():
            cfg = (db.query(Configuration)
                   .filter(Configuration.company_id == company_id)
                   .one_or_none())
            if cfg is None:
                print(f"company {company_id} : pas de configuration, ignorée")
                continue

            backup[company_id] = cfg.categories
            categories = copy.deepcopy(cfg.categories or {})

            for cat, change in cats.items():
                data = categories.get(cat)
                if not isinstance(data, dict):
                    print(f"company {company_id} : catégorie {cat} absente, ignorée")
                    continue
                before = list(data.get("keywords") or [])
                after = [k for k in before if k not in change["remove"]]
                for k in change["add"]:
                    if k not in after:
                        after.append(k)
                data["keywords"] = after
                print(f"company {company_id} / {cat}")
                print(f"   retirés : {[k for k in before if k not in after]}")
                print(f"   ajoutés : {[k for k in after if k not in before]}")

            if apply:
                cfg.categories = categories
                flag_modified(cfg, "categories")
                cfg.modifie_par = "script fix_keywords"

        if apply:
            path = Path(__file__).with_name(
                f"_backup_config_{datetime.now():%Y%m%d_%H%M%S}.json")
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            db.commit()
            print(f"\nÉcrit en base. Sauvegarde de l'ancienne config : {path}")
        else:
            db.rollback()
            print("\nSIMULATION : rien n'a été écrit. Relance avec --apply pour appliquer.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)