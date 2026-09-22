import sys
sys.path.insert(0, '.')

from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.services.config_service import get_or_create_config
from app.services.scoring_orchestrator import score_tender_full
from app.schemas.sotradies import SotradiesRaw
from datetime import datetime

with session_scope() as db:
    config = get_or_create_config(db)

    categories = config.categories or {}
    exclusions = config.exclusion_keywords or []
    seuil = config.score_decision_threshold
    rules = config.assignment_rules or {}

    print('=' * 70)
    print('CONFIGURATION')
    print('=' * 70)

    print(f'Seuil retention : {seuil}%')

    print(f'Categories ({len(categories)}) :')

    for cat_id, cat_data in categories.items():
        kw = cat_data.get('keywords', [])
        mq = cat_data.get('marques', [])
        co = cat_data.get('commercial', 'NON ASSIGNE')

        print(f'  {cat_id} :')
        print(f'    Commercial : {co}')
        print(f'    Mots-cles  : {kw[:8]}')
        print(f'    Marques    : {mq[:5]}')

    print(f'Exclusions ({len(exclusions)}) : {exclusions[:10]}')
    print(f'Regles assignation : {rules}')

    print()
    print('=' * 70)
    print('MARCHES EN BASE')
    print('=' * 70)

    total = db.query(Sotradies).count()
    retenus = db.query(Sotradies).filter_by(statut='retenu').count()
    nouveaux = db.query(Sotradies).filter_by(statut='nouveau').count()

    print(f'Total={total} | Retenus={retenus} | Nouveaux={nouveaux}')

    marches = (
        db.query(Sotradies)
        .order_by(Sotradies.date_publication.desc())
        .limit(10)
        .all()
    )

    for m in marches:
        score_info = ''

        if m.score_details:
            for cat, d in m.score_details.items():
                if isinstance(d, dict) and d.get('score', 0) > 0:
                    score_info += f" {cat}={d.get('score', 0)}%"

        print(f'  [{m.statut:8s}] {(m.objet or "")[:60]}')
        print(
            f'    Score: {score_info or "aucun match"} '
            f'| Commercial: {m.commercial_assigne or "N/A"}'
        )

    print()
    print('=' * 70)
    print('SIMULATION DE SCORING')
    print('=' * 70)

    for cat_id, cat_data in categories.items():

        kw = cat_data.get('keywords', [])

        if not kw:
            continue

        title = f'Acquisition de {kw[0]}'

        if len(kw) > 1:
            title += f' et {kw[1]}'

        fake = SotradiesRaw(
            source='test',
            objet=title,
            acheteur='Ministere Test',
            categorie='fournitures',
            date_publication=datetime.now(),
            reference='TEST-001',
            date_limite=None,
            budget_estime=None,
            lien=None,
        )

        result = score_tender_full(
            fake,
            categories,
            exclusions
        ) or {}

        best_cat = None
        best_score = 0

        for c, d in result.items():
            if isinstance(d, dict):
                s = int(d.get('score', 0) or 0)

                if s > best_score:
                    best_cat = c
                    best_score = s

        status = 'RETENU' if best_score >= seuil else 'REJETE'

        matched = []

        if best_cat and best_cat in result:
            matched = result[best_cat].get(
                'mots_cles_matches',
                []
            )

        print(
            f'  {status} | {best_score}% '
            f'| cat={best_cat} | mots={matched}'
        )

        print(f'    Titre: {title}')
        
        
