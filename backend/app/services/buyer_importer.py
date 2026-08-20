"""Lit le fichier Excel des clients/acheteurs historiques et l'importe en base."""
import pandas as pd
from sqlalchemy.orm import Session

from app.models.known_buyer import KnownBuyer

EXCEL_PATH = "data/clients_sotradies_modele.xlsx"


def import_known_buyers(db: Session, excel_path: str = EXCEL_PATH) -> int:
    df = pd.read_excel(excel_path, sheet_name="Clients Sotradies", header=3)
    df.columns = ["nom_acheteur", "variantes", "client_sotradies", "notes"]

    df = df.dropna(subset=["nom_acheteur"])
    df = df[~df["nom_acheteur"].astype(str).str.startswith("[EXEMPLE]")]

    db.query(KnownBuyer).delete()

    count = 0
    for _, row in df.iterrows():
        db.add(KnownBuyer(
            nom_acheteur=str(row["nom_acheteur"]).strip(),
            variantes=str(row["variantes"]).strip() if pd.notna(row["variantes"]) else None,
            client_sotradies=str(row["client_sotradies"]).strip() if pd.notna(row["client_sotradies"]) else "Non",
            notes=str(row["notes"]).strip() if pd.notna(row["notes"]) else None,
        ))
        count += 1

    db.commit()
    return count


if __name__ == "__main__":
    from app.core.database import session_scope

    with session_scope() as db:
        n = import_known_buyers(db)
        print(f"{n} acheteur(s) importé(s) en base")