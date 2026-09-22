"""
Envoi des alertes email — version multi-tenant.

Chaque client (Company) reçoit des alertes uniquement pour SES
CompanyTender retenus, envoyées uniquement à SES commerciaux.
"""
from datetime import datetime, date, UTC

from app.core.templates import jinja_env
from app.core.database import session_scope
from app.models.company import Company
from app.models.company_tender import CompanyTender
from app.models.commercial import Commercial
from app.models.sotradies import Sotradies
from app.models.sent_log import SentLog
from app.services.mailer import send_email
from app.services.config_service import get_or_create_config


def is_weekend(d: date | None = None) -> bool:
    d = d or datetime.now().date()
    return d.weekday() in (5, 6)


def dispatch_new_tenders(force: bool = False):
    """Alerte instantanée pour chaque CompanyTender retenu au-delà
    du seuil d'alerte de SA propre configuration client."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas d'alerte instantanée.")
        return 0

    envoyes = 0

    with session_scope() as db:
        matches = (
            db.query(CompanyTender)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.statut == "nouveau",
                CompanyTender.commercial_id.isnot(None),
            )
            .all()
        )

        for match in matches:
            config = get_or_create_config(db, company_id=match.company_id)

            if match.score < config.score_instant_alert_threshold:
                continue

            already = (
                db.query(SentLog)
                .filter_by(company_tender_id=match.id, canal="instantane")
                .first()
            )
            if already:
                continue

            commercial = (
                db.query(Commercial)
                .filter_by(id=match.commercial_id)
                .first()
            )
            # Garde-fou d'isolation : le commercial doit appartenir
            # au même client que le marché.
            if commercial is None or commercial.company_id != match.company_id:
                continue
            if not commercial.actif:
                continue

            tender = db.query(Sotradies).filter_by(id=match.tender_id).first()
            if tender is None:
                continue

            body = jinja_env.get_template("instant_alert_email.html").render(
                tender=tender, score=match.score,
            )
            success = send_email(
                commercial.email,
                f"🔴 Offre très pertinente détectée — {tender.objet[:60]}",
                body,
            )
            if not success:
                continue

            db.add(SentLog(
                company_tender_id=match.id,
                commercial=commercial.nom,
                canal="instantane",
            ))
            envoyes += 1
            print(f"[notifier] ✅ Alerte → {commercial.nom} ({commercial.email}) — score {match.score}%")

    print(f"[notifier] {envoyes} alerte(s) instantanée(s) envoyée(s)")
    return envoyes


def send_daily_digest(force: bool = False):
    """Digest quotidien : boucle sur chaque client, puis sur SES
    commerciaux actifs, avec uniquement SES marchés retenus."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de digest.")
        return 0

    envoyes = 0

    with session_scope() as db:
        companies = db.query(Company).all()

        for company in companies:
            commerciaux = (
                db.query(Commercial)
                .filter_by(company_id=company.id, actif=True)
                .all()
            )

            for commercial in commerciaux:
                matches = (
                    db.query(CompanyTender)
                    .filter(
                        CompanyTender.company_id == company.id,
                        CompanyTender.commercial_id == commercial.id,
                        CompanyTender.decision == "retenu",
                    )
                    .all()
                )

                a_envoyer = [
                    m for m in matches
                    if not db.query(SentLog).filter_by(
                        company_tender_id=m.id, canal="digest"
                    ).first()
                    and not db.query(SentLog).filter_by(
                        company_tender_id=m.id, canal="instantane"
                    ).first()
                ]

                if not a_envoyer:
                    continue

                tender_ids = [m.tender_id for m in a_envoyer]
                tenders = (
                    db.query(Sotradies)
                    .filter(Sotradies.id.in_(tender_ids))
                    .all()
                )

                subject = f"Récapitulatif quotidien — {len(tenders)} marché(s)"
                body = jinja_env.get_template("digest_email.html").render(
                    tenders=tenders, commercial=commercial.nom,
                )
                success = send_email(commercial.email, subject, body)
                if not success:
                    print(f"[notifier] ⚠️ Échec digest {commercial.email}")
                    continue

                for m in a_envoyer:
                    db.add(SentLog(
                        company_tender_id=m.id,
                        commercial=commercial.nom,
                        canal="digest",
                    ))

                envoyes += 1
                print(f"[notifier] ✅ Digest → {commercial.nom} ({company.nom}) — {len(tenders)} marché(s)")

    print(f"[notifier] {envoyes} digest(s) envoyé(s)")
    return envoyes


def send_reminders(force: bool = False):
    """Rappels J-3/J-1 par CompanyTender retenu, non traité."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de rappel.")
        return 0

    today = datetime.now().date()
    envoyes = 0

    with session_scope() as db:
        matches = (
            db.query(CompanyTender)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.commercial_id.isnot(None),
            )
            .all()
        )

        for match in matches:
            tender = db.query(Sotradies).filter_by(id=match.tender_id).first()
            if tender is None or tender.date_limite is None:
                continue

            commercial = (
                db.query(Commercial)
                .filter(
                    Commercial.id == match.commercial_id,
                    Commercial.company_id == match.company_id,
                )
                .first()
            )
            if commercial is None or not commercial.actif:
                continue

            jours_restants = (tender.date_limite.date() - today).days

            if jours_restants == 3 and not match.rappel_j3_envoye:
                body = jinja_env.get_template("reminder_email.html").render(
                    tender=tender, jours_restants=3,
                )
                if send_email(commercial.email, f"⏰ Rappel J-3 — {tender.objet[:60]}", body):
                    match.rappel_j3_envoye = datetime.now(UTC).replace(tzinfo=None)
                    envoyes += 1

            elif jours_restants == 1 and not match.rappel_j1_envoye:
                body = jinja_env.get_template("reminder_email.html").render(
                    tender=tender, jours_restants=1,
                )
                if send_email(commercial.email, f"⏰ Rappel J-1 (urgent) — {tender.objet[:60]}", body):
                    match.rappel_j1_envoye = datetime.now(UTC).replace(tzinfo=None)
                    envoyes += 1

    print(f"[notifier] {envoyes} rappel(s) envoyé(s)")
    return envoyes