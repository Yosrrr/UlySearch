"""Layer 9 — Reporting périodique automatique à la direction."""
from datetime import datetime, timedelta
from app.core.templates import jinja_env as env
from sqlalchemy import func



from app.core.config import settings
from app.core.database import SessionLocal
from app.models.sotradies import Sotradies
from app.models.sent_log import SentLog
from app.services.mailer import send_email


def send_periodic_report(days: int = 7):
    db = SessionLocal()
    depuis = datetime.utcnow() - timedelta(days=days)

    marches = db.query(Sotradies).filter(Sotradies.date_detection >= depuis).all()

    total_detectes = len(marches)
    total_retenus = sum(1 for m in marches if m.score_details and
                         max((v["score"] for v in m.score_details.values()), default=0) > 0)
    total_acheteurs_connus = sum(1 for m in marches if m.acheteur_connu == "Oui")
    total_alertes = db.query(SentLog).filter(
        SentLog.canal == "instantane", SentLog.date_envoi >= depuis
    ).count()

    par_commercial_raw = {}
    par_source_raw = {}
    for m in marches:
        if m.commercial_assigne:
            par_commercial_raw[m.commercial_assigne] = par_commercial_raw.get(m.commercial_assigne, 0) + 1
        par_source_raw[m.source] = par_source_raw.get(m.source, 0) + 1

    db.close()

    html = env.get_template("periodic_report_email.html").render(
        periode=f"{depuis.strftime('%d/%m/%Y')} — {datetime.utcnow().strftime('%d/%m/%Y')}",
        total_detectes=total_detectes,
        total_retenus=total_retenus,
        total_alertes=total_alertes,
        total_acheteurs_connus=total_acheteurs_connus,
        par_commercial=[{"commercial": k, "nombre": v} for k, v in par_commercial_raw.items()],
        par_source=[{"source": k, "nombre": v} for k, v in par_source_raw.items()],
    )

    send_email(settings.DIRECTION_EMAIL, "Rapport hebdomadaire — Veille Appels d'Offres", html)
    print(f"[reporting] Rapport envoyé à {settings.DIRECTION_EMAIL} "
          f"({total_detectes} marchés détectés sur {days} jours)")