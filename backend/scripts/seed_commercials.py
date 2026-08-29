"""
Seed initial des commerciaux — version interactive sécurisée.

Les emails sont saisis à l'exécution et ne sont jamais codés en dur.

Usage :
    python -m scripts.seed_commercials
"""
from app.core.database import session_scope
from app.models.commercial import Commercial

NOMS_COMMERCIAUX = [
    "Ramzi Trabelsi",
    "Zied Hajji",
    "Salah Gharbi",
]


def main() -> None:
    with session_scope() as db:
        for nom in NOMS_COMMERCIAUX:
            existing = db.query(Commercial).filter_by(nom=nom).first()

            if existing:
                print(f"Déjà présent : {existing.nom} <{existing.email}> actif={existing.actif}")
                changer = input("  Modifier cet email ? [o/N] : ").strip().lower()
                if changer != "o":
                    continue

                email = input(f"  Nouvel email pour {nom} : ").strip()
                if not email:
                    print("  Ignoré.")
                    continue

                existing.email = email
                existing.actif = True
                print(f"  Mis à jour : {nom} -> {email}")
                continue

            email = input(f"Email pour {nom} : ").strip()
            if not email:
                print(f"  Ignoré : {nom}")
                continue

            db.add(Commercial(nom=nom, email=email, actif=True))
            print(f"  Ajouté : {nom} -> {email}")

    print("\nSeed commercials terminé.")


if __name__ == "__main__":
    main()