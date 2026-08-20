import os

COMMERCIAL_EMAILS = {
    "Ramzi Trabelsi": os.getenv("EMAIL_RAMZI_TRABELSI", ""),
    "Zied Hajji": os.getenv("EMAIL_ZIED_HAJJI", ""),
    "Salah Gharbi": os.getenv("EMAIL_SALAH_GHARBI", ""),
}

for nom, email in COMMERCIAL_EMAILS.items():
    if not email:
        print(f"[commercials] ⚠️ Aucune adresse configurée pour {nom} — les alertes pour cette personne ne partiront pas.")