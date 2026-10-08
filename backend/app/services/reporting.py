"""Layer 9 — Rapport périodique direction.

F-033 : ne plus s'appuyer sur Sotradies.score_details / commercial_assigne
(legacy). Compteurs issus de company_tenders (+ sotradies pour détection/source).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from app.core.config import settings
from app.core.database import session_scope
from app.core.templates import jinja_env as env
from app.models.commercial import Commercial
from app.models.company_tender import CompanyTender
from app.models.sent_log import SentLog
from app.models.sotradies import Sotradies
from app.services.mailer import send_email


def send_periodic_report(days: int = 7) -> dict:
    """
    Envoie un rapport agrégé à DIRECTION_EMAIL.
    Retourne un dict de statut pour Celery / logs.
    """
    if not getattr(settings, "DIRECTION_EMAIL", None):
        print("[reporting] DIRECTION_EMAIL absent — rapport non envoyé.")
        return {"status": "skipped", "reason": "missing_direction_email"}

    maintenant = datetime.now(UTC).replace(tzinfo=None)
    depuis = maintenant - timedelta(days=days)

    with session_scope() as db:
        total_detectes = (
            db.query(func.count(Sotradies.id))
            .filter(Sotradies.date_detection >= depuis)
            .scalar()
            or 0
        )

        total_retenus = (
            db.query(func.count(CompanyTender.id))
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                Sotradies.date_detection >= depuis,
                CompanyTender.decision == "retenu",
            )
            .scalar()
            or 0
        )

        total_acheteurs_connus = (
            db.query(func.count(CompanyTender.id))
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                Sotradies.date_detection >= depuis,
                CompanyTender.decision == "retenu",
                CompanyTender.acheteur_connu == "Oui",
            )
            .scalar()
            or 0
        )

        total_alertes = (
            db.query(func.count(SentLog.id))
            .filter(
                SentLog.canal == "instantane",
                SentLog.date_envoi >= depuis,
            )
            .scalar()
            or 0
        )

        rows_com = (
            db.query(Commercial.nom, func.count(CompanyTender.id))
            .join(
                CompanyTender,
                CompanyTender.commercial_id == Commercial.id,
            )
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                Sotradies.date_detection >= depuis,
                CompanyTender.decision == "retenu",
            )
            .group_by(Commercial.nom)
            .all()
        )
        par_commercial = [
            {"commercial": (nom or "Non assigné"), "nombre": int(n)}
            for nom, n in sorted(rows_com, key=lambda x: (x[0] or ""))
        ]

        # Retenus sans commercial
        sans_com = (
            db.query(func.count(CompanyTender.id))
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                Sotradies.date_detection >= depuis,
                CompanyTender.decision == "retenu",
                CompanyTender.commercial_id.is_(None),
            )
            .scalar()
            or 0
        )
        if sans_com:
            par_commercial.append(
                {"commercial": "Non assigné", "nombre": int(sans_com)}
            )

        rows_src = (
            db.query(Sotradies.source, func.count(Sotradies.id))
            .filter(Sotradies.date_detection >= depuis)
            .group_by(Sotradies.source)
            .all()
        )
        par_source = [
            {"source": (src or "—"), "nombre": int(n)}
            for src, n in sorted(rows_src, key=lambda x: (x[0] or ""))
        ]

        html = env.get_template("periodic_report_email.html").render(
            periode=(
                f"{depuis.strftime('%d/%m/%Y')} — "
                f"{maintenant.strftime('%d/%m/%Y')}"
            ),
            total_detectes=total_detectes,
            total_retenus=total_retenus,
            total_alertes=total_alertes,
            total_acheteurs_connus=total_acheteurs_connus,
            par_commercial=par_commercial,
            par_source=par_source,
        )

    success = send_email(
        settings.DIRECTION_EMAIL,
        "Rapport hebdomadaire — Veille Appels d'Offres",
        html,
    )

    if success:
        print(
            f"[reporting] Rapport envoyé à {settings.DIRECTION_EMAIL} "
            f"(détectés={total_detectes}, retenus={total_retenus}, {days} j)"
        )
        return {
            "status": "sent",
            "total_detectes": total_detectes,
            "total_retenus": total_retenus,
        }

    print("[reporting] Échec envoi rapport direction.")
    return {
        "status": "error",
        "total_detectes": total_detectes,
        "total_retenus": total_retenus,
    }