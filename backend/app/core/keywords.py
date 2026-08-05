"""
Dictionnaire de mots-clés par catégorie (Layer 4, Tier 1).

⚠️ Version de calibrage initiale, basée sur :
- les mots-clés utilisés aujourd'hui manuellement par Sotradies (camion,
  tractopelle, chargeuse, chariot, groupe électrogène, marques associées)
- la liste de marques confirmée en réunion client

À AFFINER avec le "dictionnaire de mots-clés initial" que le client doit
fournir (Excel/CSV/PDF — item CRITIQUE de la liste des livrables attendus),
et avec les 20-30 exemples annotés (pertinent / pas pertinent).
"""

# Catégorie -> (mots-clés, marques associées, commercial assigné)
# Le commercial est None quand la réunion client n'a pas encore tranché
# l'assignation pour cette catégorie (à confirmer explicitement).
CATEGORIES = {
    "MATERIEL_ROULANT": {
        "commercial": "Ramzi Trabelsi",
        "marques": ["IVECO", "Otokar"],
        "keywords": [
            "camion", "camionnette", "poids lourd", "vehicule utilitaire",
            "tracteur routier", "benne", "citerne", "fourgon",
            "materiel roulant", "autobus", "autocar",
        ],
    },
    "ENGINS_TP": {
        "commercial": "Zied Hajji",
        "marques": ["CASE", "HAMM", "Wirtgen", "Kleemann", "Schwing Stetter"],
        "keywords": [
            "tractopelle", "chargeuse", "pelle hydraulique", "niveleuse",
            "terrassement", "genie civil", "engin tp", "compacteur",
            "bulldozer", "concasseur", "malaxeur", "pompe a beton",
        ],
    },
    "MANUTENTION": {
        "commercial": "Salah Gharbi",
        "marques": ["Hyster", "CG Est Manutention"],
        "keywords": [
            "chariot", "chariot elevateur", "transpalette",
            "materiel de levage", "engin de manutention", "manutention",
            "entrepot",
        ],
    },
    "ENGINS_SPECIAUX": {
        "commercial": None,  # ⚠️ à confirmer avec le client
        "marques": [],
        "keywords": ["engin special"],
    },
    "GROUPES_ELECTROGENES": {
        "commercial": None,  # ⚠️ à confirmer avec le client
        "marques": ["ALMIG", "Himoinsa"],
        "keywords": ["groupe electrogene", "compresseur", "installation electrique"],
    },
}

# Mots-clés qui excluent systématiquement un marché, quelle que soit la catégorie
EXCLUSION_KEYWORDS = [
    "papeterie", "fourniture de bureau", "produits alimentaires",
    "nettoyage", "gardiennage",
]