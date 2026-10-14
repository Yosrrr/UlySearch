"""
Envoi des alertes email — version multi-tenant.

Chaque client (Company) reçoit des alertes uniquement pour SES
CompanyTender retenus, envoyées uniquement à SES commerciaux.

OPS-004 : l'envoi est RÉSERVÉ avant l'appel SMTP (_claim_send), protégé par
l'index unique partiel uq_sent_log_company_tender_canal. Deux workers
concurrents ne peuvent donc pas envoyer le même mail.
"""
import html
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import session_scope
from app.core.templates import jinja_env
from app.models.commercial import Commercial
from app.models.company import Company
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.sent_log import SentLog
from app.models.sotradies import Sotradies
from app.services.mailer import send_email


# ──────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────

def is_weekend(d: date | None = None) -> bool:
    d = d or datetime.now().date()
    return d.weekday() in (5, 6)


def _safe_subject(text: str, max_len: int = 60) -> str:
    """Sujet d'email : tronqué, sans balises HTML."""
    return html.escape(str(text or "")[:max_len])


def _sent_ids(db: Session, canal: str) -> set[int]:
    """Ensemble des company_tender_id déjà envoyés pour ce canal."""
    rows = db.query(SentLog.company_tender_id).filter_by(canal=canal).all()
    return {r[0] for r in rows if r[0] is not None}


def _configs_by_company(db: Session) -> dict[int, Configuration]:
    """Charge toutes les configurations en une seule requête."""
    return {c.company_id: c for c in db.query(Configuration).all()}


def _claim_send(
    db: Session,
    *,
    company_tender_id: int,
    canal: str,
    commercial: str,
    sotradies_id: str | None = None,
) -> SentLog | None:
    """
    OPS-004 : réserve l'envoi AVANT d'appeler SMTP.

    Retourne None si la ligne existe déjà (un autre worker, ou une passe
    précédente, a déjà réservé/envoyé). Le SAVEPOINT isole l'échec :
    la transaction en cours reste valide.
    """
    entry = SentLog(
        company_tender_id=company_tender_id,
        sotradies_id=sotradies_id,
        commercial=commercial,
        canal=canal,
    )
    try:
        with db.begin_nested():
            db.add(entry)
            db.flush()
    except IntegrityError:
        return None
    return entry


def _release(db: Session, entries) -> None:
    """Libère des réservations après un échec SMTP ou template."""
    for e in entries:
        db.delete(e)
    db.flush()


# ──────────────────────────────────────────────────────────────
# Alerte instantanée
# ──────────────────────────────────────────────────────────────

def dispatch_new_tenders(force: bool = False) -> int:
    """Alerte instantanée pour chaque CompanyTender retenu au-delà
    du seuil d'alerte de SA propre configuration client."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas d'alerte instantanée.")
        return 0

    envoyes = 0

    with session_scope() as db:
        configs = _configs_by_company(db)
        deja_envoyes = _sent_ids(db, "instantane")

        # Alerte instantanée = offres détectées récemment uniquement.
        # Un recalcul ne transforme pas une vieille offre en urgence.
        cutoff_instant = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48)
        matches = (
            db.query(CompanyTender)
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.statut == "nouveau",
                CompanyTender.commercial_id.isnot(None),
                Sotradies.date_detection >= cutoff_instant,
                or_(
                    CompanyTender.feedback.is_(None),
                    CompanyTender.feedback != "pas_pertinent",
                ),
            )
            .all()
        )

        commercial_ids = {m.commercial_id for m in matches}
        tender_ids = {m.tender_id for m in matches}

        commerciaux = {
            c.id: c
            for c in db.query(Commercial).filter(Commercial.id.in_(commercial_ids)).all()
        } if commercial_ids else {}
        tenders = {
            t.id: t
            for t in db.query(Sotradies).filter(Sotradies.id.in_(tender_ids)).all()
        } if tender_ids else {}

        for match in matches:
            if match.id in deja_envoyes:
                continue

            config = configs.get(match.company_id)
            if config is None or match.score < config.score_instant_alert_threshold:
                continue

            commercial = commerciaux.get(match.commercial_id)
            if (
                commercial is None
                or commercial.company_id != match.company_id
                or not commercial.actif
            ):
                continue

            tender = tenders.get(match.tender_id)
            if tender is None:
                continue

            try:
                body = jinja_env.get_template("instant_alert_email.html").render(
                    tender=tender,
                    score=match.score,
                )
            except Exception as exc:
                print(f"[notifier] ⚠️ Template instantané : {exc}")
                continue

            # OPS-004 : réserver AVANT d'envoyer
            claim = _claim_send(
                db,
                company_tender_id=match.id,
                canal="instantane",
                commercial=commercial.nom,
                sotradies_id=match.tender_id,
            )
            if claim is None:
                continue

            subject = f"🔴 Alerte marché — {_safe_subject(tender.objet)}"
            if not send_email(commercial.email, subject, body):
                _release(db, [claim])
                print(f"[notifier] ⚠️ Échec envoi instantané → {commercial.email}")
                continue

            db.commit()                      # chaque envoi réussi est durable immédiatement
            deja_envoyes.add(match.id)
            envoyes += 1
            print(
                f"[notifier] ✅ Alerte → {commercial.nom} ({commercial.email})"
                f" — score {match.score}%"
            )

    print(f"[notifier] {envoyes} alerte(s) instantanée(s) envoyée(s)")
    return envoyes


# ──────────────────────────────────────────────────────────────
# Digest quotidien
# ──────────────────────────────────────────────────────────────

def _digest_target_date(value: date | None = None) -> date:
    """Date UTC affichée dans le digest."""
    return value or datetime.now(UTC).date()


def send_daily_digest(
    target_date: date | None = None,
    force: bool = False,
) -> int:
    """Envoie les marchés retenus jamais notifiés (ni instantané, ni digest).

    Le journal d'envoi est la source de vérité : pas de fenêtre de détection,
    donc aucune perte après un week-end ou une panne du worker.
    """
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de digest.")
        return 0

    target_date = _digest_target_date(target_date)
    envoyes = 0

    with session_scope() as db:
        deja_tous = _sent_ids(db, "instantane") | _sent_ids(db, "digest")

        for company in db.query(Company).all():
            commerciaux = (
                db.query(Commercial)
                .filter_by(company_id=company.id, actif=True)
                .all()
            )

            for commercial in commerciaux:
                matches = (
                    db.query(CompanyTender)
                    .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
                    .filter(
                        CompanyTender.company_id == company.id,
                        CompanyTender.commercial_id == commercial.id,
                        CompanyTender.decision == "retenu",
                        or_(
                            CompanyTender.feedback.is_(None),
                            CompanyTender.feedback != "pas_pertinent",
                        ),
                    )
                    .all()
                )

                a_envoyer = [m for m in matches if m.id not in deja_tous]
                if not a_envoyer:
                    continue

                # OPS-004 : réserver chaque offre AVANT de construire le mail,
                # pour que le contenu reflète exactement ce qui est réservé.
                claims = []
                for m in a_envoyer:
                    e = _claim_send(
                        db,
                        company_tender_id=m.id,
                        canal="digest",
                        commercial=commercial.nom,
                        sotradies_id=m.tender_id,
                    )
                    if e is not None:
                        claims.append((m, e))
                if not claims:
                    continue

                tender_ids = [m.tender_id for m, _ in claims]
                tenders = (
                    db.query(Sotradies)
                    .filter(Sotradies.id.in_(tender_ids))
                    .all()
                )

                try:
                    body = jinja_env.get_template("digest_email.html").render(
                        tenders=tenders,
                        commercial=commercial.nom,
                        date=target_date,
                    )
                except Exception as exc:
                    print(f"[notifier] ⚠️ Template digest : {exc}")
                    _release(db, [e for _, e in claims])
                    continue

                subject = (
                    f"Récapitulatif du {target_date.strftime('%d/%m/%Y')}"
                    f" — {len(tenders)} marché(s) pour {html.escape(commercial.nom)}"
                )
                if not send_email(commercial.email, subject, body):
                    _release(db, [e for _, e in claims])
                    print(f"[notifier] ⚠️ Échec digest → {commercial.email}")
                    continue

                db.commit()
                deja_tous.update(m.id for m, _ in claims)
                envoyes += 1
                print(
                    f"[notifier] ✅ Digest → {commercial.nom} ({company.nom})"
                    f" — {len(tenders)} marché(s)"
                )

    print(f"[notifier] {envoyes} digest(s) envoyé(s)")
    return envoyes


# ──────────────────────────────────────────────────────────────
# Rappels J-3 / J-1
# ──────────────────────────────────────────────────────────────

def send_reminders(force: bool = False) -> int:
    """Rappels J-3 / J-1 par CompanyTender retenu, non traité.

    Idempotence assurée par rappel_j3_envoye / rappel_j1_envoye sur
    CompanyTender (pas de SentLog ici). Fenêtres tolérantes pour ne pas
    manquer un rappel si le worker ne tourne pas le jour exact.
    """
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de rappel.")
        return 0

    today = datetime.now(UTC).date()
    now = datetime.now(UTC).replace(tzinfo=None)
    envoyes = 0

    with session_scope() as db:
        matches = (
            db.query(CompanyTender)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.commercial_id.isnot(None),
                CompanyTender.statut.notin_(["gagne", "perdu", "sans_suite"]),
                or_(
                    CompanyTender.feedback.is_(None),
                    CompanyTender.feedback != "pas_pertinent",
                ),
            )
            .all()
        )

        tender_ids = {m.tender_id for m in matches}
        commercial_ids = {m.commercial_id for m in matches}

        tenders = {
            t.id: t
            for t in db.query(Sotradies).filter(Sotradies.id.in_(tender_ids)).all()
        } if tender_ids else {}
        commerciaux = {
            c.id: c
            for c in db.query(Commercial)
            .filter(Commercial.id.in_(commercial_ids), Commercial.actif.is_(True))
            .all()
        } if commercial_ids else {}

        for match in matches:
            tender = tenders.get(match.tender_id)
            if tender is None or tender.date_limite is None:
                continue

            commercial = commerciaux.get(match.commercial_id)
            if commercial is None or commercial.company_id != match.company_id:
                continue

            jours = (tender.date_limite.date() - today).days

            # J-3 : fenêtre tolérante 1..3 jours
            if 1 <= jours <= 3 and not match.rappel_j3_envoye:
                try:
                    body = jinja_env.get_template("reminder_email.html").render(
                        tender=tender, jours_restants=jours,
                    )
                except Exception as exc:
                    print(f"[notifier] ⚠️ Template rappel J-3 : {exc}")
                    continue

                if send_email(
                    commercial.email,
                    f"⏰ Rappel J-{jours} — {_safe_subject(tender.objet)}",
                    body,
                ):
                    match.rappel_j3_envoye = now
                    db.commit()
                    envoyes += 1
                    print(f"[notifier] ✅ Rappel J-{jours} → {commercial.nom}")

            # J-1 : rappel distinct et complémentaire
            elif jours == 1 and not match.rappel_j1_envoye:
                try:
                    body = jinja_env.get_template("reminder_email.html").render(
                        tender=tender, jours_restants=1,
                    )
                except Exception as exc:
                    print(f"[notifier] ⚠️ Template rappel J-1 : {exc}")
                    continue

                if send_email(
                    commercial.email,
                    f"⏰ Rappel J-1 (urgent) — {_safe_subject(tender.objet)}",
                    body,
                ):
                    match.rappel_j1_envoye = now
                    db.commit()
                    envoyes += 1
                    print(f"[notifier] ✅ Rappel J-1 urgent → {commercial.nom}")

    print(f"[notifier] {envoyes} rappel(s) envoyé(s)")
    return envoyes