"""
Sauvegarde le contenu brut scrapé d'un marché (métadonnées liste + texte
de la page de détail) dans un fichier .txt — un fichier par offre, avant
tout appel au modèle local (demande direction du 17/08/2026).
"""
from pathlib import Path

RAW_DUMP_DIR = Path("data/raw_scrapes")
RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)


def dump_tender_to_txt(tender_id: str, tender, detail_text: str) -> Path:
    """tender : SotradiesRaw déjà scrapé. tender_id : hash stable (compute_hash)."""
    path = RAW_DUMP_DIR / f"{tender.source}_{tender_id}.txt"

    content = (
        f"SOURCE: {tender.source}\n"
        f"REFERENCE: {tender.reference or ''}\n"
        f"OBJET: {tender.objet}\n"
        f"ACHETEUR: {tender.acheteur}\n"
        f"CATEGORIE_SITE: {tender.categorie or ''}\n"
        f"DATE_PUBLICATION: {tender.date_publication or ''}\n"
        f"DATE_LIMITE: {tender.date_limite or ''}\n"
        f"LIEN: {tender.lien}\n"
        f"---\n"
        f"{detail_text}\n"
    )

    path.write_text(content, encoding="utf-8")
    return path