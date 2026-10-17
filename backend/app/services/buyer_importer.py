"""Lit le fichier Excel des clients/acheteurs historiques et l'importe en base."""
import pandas as pd
from sqlalchemy.orm import Session
from app.core.paths import BUYERS_TEMPLATE as EXCEL_PATH
from app.models.known_buyer import KnownBuyer


def import_known_buyers(
    db: Session,
    excel_path: str = EXCEL_PATH,
    company_id: int | None = None,
    replace: bool = False,
) -> int:
    df = pd.read_excel(excel_path, sheet_name="Clients Sotradies", header=3)
    df.columns = ["nom_acheteur", "variantes", "client_sotradies", "notes"]
    df = df.dropna(subset=["nom_acheteur"])
    df = df[~df["nom_acheteur"].astype(str).str.startswith("[EXEMPLE]")]

    # TECH-004 : un fichier vide ne doit pas effacer la liste existante
    if df.empty:
        raise ValueError(
            "Fichier vide : aucun acheteur importé, la liste existante est conservée."
        )

    scope = db.query(KnownBuyer)
    if company_id is None:
        scope = scope.filter(KnownBuyer.company_id.is_(None))
    else:
        scope = scope.filter(KnownBuyer.company_id == company_id)

    if replace:
        # Remplacement total : uniquement sur demande explicite (flag API)
        scope.delete(synchronize_session=False)
        existants: dict[str, KnownBuyer] = {}
    else:
        # TECH-004 : upsert par défaut, rien n'est supprimé
        existants = {b.nom_acheteur.strip().lower(): b for b in scope.all()}

    count = 0
    for _, row in df.iterrows():
        nom = str(row["nom_acheteur"]).strip()
        variantes = str(row["variantes"]).strip() if pd.notna(row["variantes"]) else None
        client = str(row["client_sotradies"]).strip() if pd.notna(row["client_sotradies"]) else "Non"
        notes = str(row["notes"]).strip() if pd.notna(row["notes"]) else None

        buyer = existants.get(nom.lower())
        if buyer:
            buyer.variantes = variantes
            buyer.client_sotradies = client
            buyer.notes = notes
        else:
            db.add(KnownBuyer(
                company_id=company_id,
                nom_acheteur=nom,
                variantes=variantes,
                client_sotradies=client,
                notes=notes,
            ))
        count += 1

    db.commit()
    return count