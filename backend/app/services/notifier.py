"""
Envoi des alertes email aux commerciaux :
- Alerte instantanée (score > seuil)
- Digest quotidien
- Rappels J-3 / J-1

Les emails des commerciaux sont désormais lus depuis la table `commercials`
(base de données) et non plus depuis un dictionnaire statique.
"""
from datetime import datetime, date

from app.core.templates import jinja_env
from app.core.commercials import get_email_for_commercial, get_all_active_commercials

from app.core.database import session_scope
from app.models.sotradies import Sotradies
from app.models.sent_log import SentLog
from app.services.mailer import send_email
from app.services.config_service import get_or_create_config


def is_weekend(d: date | None = None) -> bool:
    d = d or datetime.now().date()
    return d.weekday() in (5, 6)


def dispatch_new_tenders(force: bool = False):
    """Envoie une alerte instantanée pour chaque nouveau marché
    dont le score dépasse le seuil configuré en administration."""
    if is_weekend() and not force:
        print("[notifier] Week-end : silence radio, aucun envoi.")
        return

    envoyes = 0
    with session_scope() as db:
        seuil = get_or_create_config(db).score_instant_alert_threshold
        tenders = db.query(Sotradies).filter(Sotradies.statut == "nouveau").all()

        for t in tenders:
            if not t.commercial_assigne or not t.score_details:
                continue

            best_score = max(
                (v["score"] for v in t.score_details.values()),
                default=0,
            )
            if best_score <= seuil:
                continue

            already_sent = (
                db.query(SentLog)
                .filter_by(sotradies_id=t.id, canal="instantane")
                .first()
            )
            if already_sent:
                continue

            # Email lu depuis la base de données
            email = get_email_for_commercial(db, t.commercial_assigne)
            if not email:
                continue

            html = jinja_env.get_template("instant_alert_email.html").render(
                tender=t,
                score=best_score,
            )
            success = send_email(
                email,
                f"🔴 Offre très pertinente détectée — {t.objet[:60]}",
                html,
            )
            if not success:
                # Non marqué comme envoyé : sera retenté au prochain passage
                continue

            db.add(
                SentLog(
                    sotradies_id=t.id,
                    commercial=t.commercial_assigne,
                    canal="instantane",
                )
            )
            envoyes += 1
            print(
                f"[notifier] ✅ Alerte envoyée à {t.commercial_assigne} "
                f"({email}) — score {best_score}%"
            )

    print(f"[notifier] {envoyes} alerte(s) instantanée(s) envoyée(s)")
    return envoyes


def send_daily_digest(force: bool = False):
    """Envoie le récapitulatif quotidien à chaque commercial actif."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de digest.")
        return

    with session_scope() as db:
        # Commerciaux lus depuis la base de données
        commerciaux = get_all_active_commercials(db)

        if not commerciaux:
            print("[notifier] ⚠️ Aucun commercial actif en base.")
            return

        for c in commerciaux:
            commercial = c.nom
            email = c.email

            tenders = (
                db.query(Sotradies)
                .filter_by(commercial_assigne=commercial, statut="nouveau")
                .all()
            )

            a_envoyer = [
                t for t in tenders
                if not db.query(SentLog).filter_by(
                    sotradies_id=t.id,
                    commercial=commercial,
                    canal="digest",
                ).first()
                and not db.query(SentLog).filter_by(
                    sotradies_id=t.id,
                    commercial=commercial,
                    canal="instantane",
                ).first()
            ]

            html = jinja_env.get_template("digest_email.html").render(
                tenders=a_envoyer,
                commercial=commercial,
            )
            subject = f"Récapitulatif quotidien — {len(a_envoyer)} marché(s)"
            success = send_email(email, subject, html)

            if not success:
                print(
                    f"[notifier] ⚠️ Échec envoi digest à {commercial} "
                    "— retenté au prochain passage"
                )
                continue

            for t in a_envoyer:
                db.add(
                    SentLog(
                        sotradies_id=t.id,
                        commercial=commercial,
                        canal="digest",
                    )
                )
            print(
                f"[notifier] ✅ Digest envoyé à {commercial} "
                f"({email}) — {len(a_envoyer)} marché(s)"
            )


def send_reminders(force: bool = False):
    """Rappel J-3 et J-1 avant la date limite pour les marchés
    non encore traités. Respecte la règle silence week-end."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de rappel.")
        return

    today = datetime.now().date()
    envoyes = 0

    with session_scope() as db:
        marches = (
            db.query(Sotradies)
            .filter(
                Sotradies.statut == "nouveau",
                Sotradies.date_limite.isnot(None),
                Sotradies.commercial_assigne.isnot(None),
            )
            .all()
        )

        for t in marches:
            jours_restants = (t.date_limite.date() - today).days

            # Email lu depuis la base de données
            email = get_email_for_commercial(db, t.commercial_assigne)
            if not email:
                continue

            if jours_restants == 3 and not t.rappel_j3_envoye:
                html = jinja_env.get_template("reminder_email.html").render(
                    tender=t,
                    jours_restants=3,
                )
                if send_email(email, f"⏰ Rappel J-3 — {t.objet[:60]}", html):
                    t.rappel_j3_envoye = datetime.utcnow()
                    envoyes += 1

            elif jours_restants == 1 and not t.rappel_j1_envoye:
                html = jinja_env.get_template("reminder_email.html").render(
                    tender=t,
                    jours_restants=1,
                )
                if send_email(email, f"⏰ Rappel J-1 (urgent) — {t.objet[:60]}", html):
                    t.rappel_j1_envoye = datetime.utcnow()
                    envoyes += 1

    print(f"[notifier] {envoyes} rappel(s) envoyé(s)")
    return envoyes