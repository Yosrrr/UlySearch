from datetime import datetime, date

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.commercials import COMMERCIAL_EMAILS
from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.models.sent_log import SentLog
from app.services.mailer import send_email
from app.services.config_service import get_or_create_config


env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)


def is_weekend(d: date | None = None) -> bool:
    d = d or datetime.now().date()
    return d.weekday() in (5, 6)


def dispatch_new_tenders(force: bool = False):
    if is_weekend():
        print("[notifier] Week-end : silence radio, aucun envoi.")
        return

    envoyes = 0
    with session_scope() as db:
        seuil = get_or_create_config(db).score_instant_alert_threshold
        tenders = db.query(Sotradies).filter(Sotradies.statut == "nouveau").all()

        for t in tenders:
            if not t.commercial_assigne or not t.score_details:
                continue

            best_score = max((v["score"] for v in t.score_details.values()), default=0)
            if best_score <= seuil:
                continue

            if db.query(SentLog).filter_by(sotradies_id=t.id, canal="instantane").first():
                continue

            email = COMMERCIAL_EMAILS.get(t.commercial_assigne)
            if not email:
                print(f"[notifier] ⚠️ Pas d'email connu pour {t.commercial_assigne}")
                continue

            html = env.get_template("instant_alert_email.html").render(tender=t, score=best_score)
            success = send_email(email, f"🔴 Offre très pertinente détectée — {t.objet[:60]}", html)
            if not success:
                continue  # non marqué envoyé : sera retenté au prochain passage

            db.add(SentLog(sotradies_id=t.id, commercial=t.commercial_assigne, canal="instantane"))
            envoyes += 1
            print(f"[notifier] ✅ Alerte envoyée à {t.commercial_assigne} ({email}) — score {best_score}%")
    # commit/close automatiques via session_scope()

    print(f"[notifier] {envoyes} alerte(s) instantanée(s) envoyée(s)")
    return envoyes


def send_daily_digest(force: bool = False):
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de digest.")
        return

    with session_scope() as db:
        for commercial, email in COMMERCIAL_EMAILS.items():
            tenders = db.query(Sotradies).filter_by(commercial_assigne=commercial, statut="nouveau").all()
            a_envoyer = [
                t for t in tenders
                if not db.query(SentLog).filter_by(sotradies_id=t.id, commercial=commercial, canal="digest").first()
                and not db.query(SentLog).filter_by(sotradies_id=t.id, commercial=commercial, canal="instantane").first()
            ]

            html = env.get_template("digest_email.html").render(tenders=a_envoyer, commercial=commercial)
            subject = f"Récapitulatif quotidien — {len(a_envoyer)} marché(s)"
            success = send_email(email, subject, html)
            if not success:
                print(f"[notifier] ⚠️ Échec envoi digest à {commercial}, aucun SentLog créé — retenté au prochain passage")
                continue

            for t in a_envoyer:
                db.add(SentLog(sotradies_id=t.id, commercial=commercial, canal="digest"))
            print(f"[notifier] ✅ Digest envoyé à {commercial} ({email}) — {len(a_envoyer)} marché(s)")


def send_reminders(force: bool = False):
    """
    Rappel J-3 et J-1 avant la date limite, pour tout marché non encore
    traité (statut='nouveau'). Respecte la règle silence week-end.
    """
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de rappel.")
        return

    today = datetime.now().date()
    envoyes = 0

    with session_scope() as db:
        marches = db.query(Sotradies).filter(
            Sotradies.statut == "nouveau",
            Sotradies.date_limite.isnot(None),
            Sotradies.commercial_assigne.isnot(None),
        ).all()

        for t in marches:
            jours_restants = (t.date_limite.date() - today).days
            email = COMMERCIAL_EMAILS.get(t.commercial_assigne)
            if not email:
                continue

            if jours_restants == 3 and not t.rappel_j3_envoye:
                html = env.get_template("reminder_email.html").render(tender=t, jours_restants=3)
                if send_email(email, f"⏰ Rappel J-3 — {t.objet[:60]}", html):
                    t.rappel_j3_envoye = datetime.utcnow()
                    envoyes += 1

            elif jours_restants == 1 and not t.rappel_j1_envoye:
                html = env.get_template("reminder_email.html").render(tender=t, jours_restants=1)
                if send_email(email, f"⏰ Rappel J-1 (urgent) — {t.objet[:60]}", html):
                    t.rappel_j1_envoye = datetime.utcnow()
                    envoyes += 1

    print(f"[notifier] {envoyes} rappel(s) envoyé(s)")
    return envoyes