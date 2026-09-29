"""
Sources publiques autorisées dans les suggestions d'onboarding.

Ce catalogue :
- ne crée aucune source ;
- ne change pas les abonnements ;
- ne désactive pas les autres collecteurs ;
- limite uniquement les sources que l'IA peut proposer.

Les identifiants correspondent à votre base actuelle.
"""

PUBLIC_ONBOARDING_SOURCES = {
    23: {
        "nom": "ONMP",
        "type": "dedie",
        "hosts": {
            "marchespublics.gov.tn",
            "www.marchespublics.gov.tn",
        },
        "pays": ["TN"],
        "international": False,
        "description": (
            "Portail généraliste des marchés publics tunisiens. "
            "Les annonces doivent ensuite être filtrées selon "
            "l'activité du client."
        ),
    },
    24: {
        "nom": "TUNEPS",
        "type": "dedie",
        "hosts": {
            "tuneps.tn",
            "www.tuneps.tn",
        },
        "pays": ["TN"],
        "international": False,
        "description": (
            "Plateforme généraliste de marchés publics tunisiens. "
            "Collecte avec le connecteur dédié existant."
        ),
    },
}