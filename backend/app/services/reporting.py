"""Layer 9 — Reporting périodique automatique à la direction."""
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import session_scope
from app.core.templates import jinja_env as env
from app.models.sent_log import SentLog
from app.models.sotradies import Sotradies
from app.services.mailer import send_email


def _best_score(score_details: dict | None) -> int:
    if not score_details:
        return 0
    best = 0
    for value in score_details.values():
        if isinstance(value, dict):
            score = int(value.get("score", 0) or 0)
            if score > best:
                best = score
    return best


def send_periodic_report(days: int = 7) -> dict:
    """
    Envoie un rapport périodique à la direction.

    Retourne un dict de statut exploitable par Celery/logs.
    """
    if not settings.DIRECTION_EMAIL:
        print("[reporting] DIRECTION_EMAIL absent — rapport non envoyé.")
        return {"status": "skipped", "reason": "missing_direction_email"}

    depuis = datetime.utcnow() - timedelta(days=days)

    with session_scope() as db:
        marches = (
            db.query(Sotradies)
            .filter(Sotradies.date_detection >= depuis)
            .all()
        )

        total_detectes = len(marches)
        total_retenus = sum(1 for m in marches if _best_score(m.score_details) > 0)
        total_acheteurs_connus = sum(1 for m in marches if m.acheteur_connu == "Oui")

        total_alertes = (
            db.query(SentLog)
            .filter(
                SentLog.canal == "instantane",
                SentLog.date_envoi >= depuis,
            )
            .count()
        )

        par_commercial_raw = {}
        par_source_raw = {}

        for m in marches:
            if m.commercial_assigne:
                par_commercial_raw[m.commercial_assigne] = (
                    par_commercial_raw.get(m.commercial_assigne, 0) + 1
                )
            par_source_raw[m.source] = par_source_raw.get(m.source, 0) + 1

    html = env.get_template("periodic_report_email.html").render(
        periode=f"{depuis.strftime('%d/%m/%Y')} — {datetime.utcnow().strftime('%d/%m/%Y')}",
        total_detectes=total_detectes,
        total_retenus=total_retenus,
        total_alertes=total_alertes,
        total_acheteurs_connus=total_acheteurs_connus,
        par_commercial=[
            {"commercial": k, "nombre": v}
            for k, v in sorted(par_commercial_raw.items())
        ],
        par_source=[
            {"source": k, "nombre": v}
            for k, v in sorted(par_source_raw.items())
        ],
    )

    success = send_email(
        settings.DIRECTION_EMAIL,
        "Rapport hebdomadaire — Veille Appels d'Offres",
        html,
    )

    if success:
        print(
            f"[reporting] Rapport envoyé à {settings.DIRECTION_EMAIL} "
            f"({total_detectes} marchés détectés sur {days} jours)"
        )
        return {"status": "sent", "total_detectes": total_detectes}

    print("[reporting] Échec envoi rapport direction.")
    return {"status": "error", "total_detectes": total_detectes}