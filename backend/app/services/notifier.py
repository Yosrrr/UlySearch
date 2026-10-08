"""
Envoi des alertes email — version multi-tenant.

Chaque client (Company) reçoit des alertes uniquement pour SES
CompanyTender retenus, envoyées uniquement à SES commerciaux.
"""
import html
from collections import defaultdict
from datetime import UTC, date, datetime
from datetime import timedelta
from sqlalchemy import or_
from app.models.sotradies import Sotradies
from sqlalchemy.orm import Session
from app.core.database import session_scope
from app.core.templates import jinja_env
from app.models.commercial import Commercial
from app.models.company import Company
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.sent_log import SentLog

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
    """Retourne l'ensemble des company_tender_id déjà envoyés pour ce canal."""
    rows = db.query(SentLog.company_tender_id).filter_by(canal=canal).all()
    return {r[0] for r in rows}


def _configs_by_company(db: Session) -> dict[int, object]:
    """Charge toutes les configurations en une seule requête."""
    configs = db.query(Configuration).all()
    return {c.company_id: c for c in configs}


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
        # Chargement en une seule requête
        configs = _configs_by_company(db)
        deja_envoyes = _sent_ids(db, "instantane")

        # Alerte instantanée = offres détectées récemment uniquement.
        # Un recalcul ou un nouveau score ne transforme pas une vieille offre en urgence.
        cutoff_instant = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48)
        matches = (
            db.query(CompanyTender)
            .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.statut == "nouveau",
                CompanyTender.commercial_id.isnot(None),
                Sotradies.date_detection >= cutoff_instant,
                CompanyTender.statut.notin_(["gagne", "perdu", "sans_suite"]),
                or_(CompanyTender.feedback.is_(None),
                    CompanyTender.feedback != "pas_pertinent"),
            )
            .all()
        
        )

        # Charger tous les commerciaux et marchés concernés en une fois
        commercial_ids = {m.commercial_id for m in matches}
        tender_ids = {m.tender_id for m in matches}

        commerciaux = {
            c.id: c
            for c in db.query(Commercial)
            .filter(Commercial.id.in_(commercial_ids))
            .all()
        }
        tenders = {
            t.id: t
            for t in db.query(Sotradies)
            .filter(Sotradies.id.in_(tender_ids))
            .all()
        }

        for match in matches:
            if match.id in deja_envoyes:
                continue

            config = configs.get(match.company_id)
            if config is None:
                continue
            if match.score < config.score_instant_alert_threshold:
                continue

            commercial = commerciaux.get(match.commercial_id)
            if commercial is None or commercial.company_id != match.company_id:
                continue
            if not commercial.actif:
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

            success = send_email(
                commercial.email,
                f"🔴 Offre très pertinente — {_safe_subject(tender.objet)}",
                body,
            )
            if not success:
                print(f"[notifier] ⚠️ Échec envoi instantané → {commercial.email}")
                continue

            db.add(SentLog(
                company_tender_id=match.id,
                commercial=commercial.nom,
                canal="instantane",
            ))
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

def send_daily_digest(
    target_date: date | None = None,
    force: bool = False,
) -> int:
    """Digest quotidien : uniquement les marchés retenus à la date cible,
    non encore envoyés (ni en instantané ni en digest)."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de digest.")
        return 0

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=4)
    envoyes = 0

    with session_scope() as db:
        deja_instantane = _sent_ids(db, "instantane")
        deja_digest = _sent_ids(db, "digest")
        deja_tous = deja_instantane | deja_digest

        companies = db.query(Company).all()

        for company in companies:
            commerciaux = (
                db.query(Commercial)
                .filter_by(company_id=company.id, actif=True)
                .all()
            )

            for commercial in commerciaux:
                # Marchés retenus pour ce commercial, détectés à la date cible
                matches = (
                    db.query(CompanyTender)
                    .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
                    .filter(
                        CompanyTender.company_id == company.id,
                        CompanyTender.commercial_id == commercial.id,
                        CompanyTender.decision == "retenu",
                        or_(CompanyTender.feedback.is_(None),
                            CompanyTender.feedback != "pas_pertinent"),
                    )
                    .all()
                )

                # Exclure ceux déjà envoyés
                a_envoyer = [m for m in matches if m.id not in deja_tous]
                if not a_envoyer:
                    continue

                tender_ids = [m.tender_id for m in a_envoyer]
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
                    continue

                subject = (
                    f"Récapitulatif du {target_date.strftime('%d/%m/%Y')}"
                    f" — {len(tenders)} marché(s) pour {html.escape(commercial.nom)}"
                )
                success = send_email(commercial.email, subject, body)

                if not success:
                    print(f"[notifier] ⚠️ Échec digest → {commercial.email}")
                    # On continue : les SentLog ne sont PAS créés,
                    # le digest sera retenté au prochain appel.
                    continue

                for m in a_envoyer:
                    db.add(SentLog(
                        company_tender_id=m.id,
                        commercial=commercial.nom,
                        canal="digest",
                    ))
                    deja_tous.add(m.id)

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
    """Rappels J-3/J-1 par CompanyTender retenu, non traité.
    Fenêtre tolérante : <= 3 jours pour J-3, <= 1 jour pour J-1,
    afin de ne pas manquer un rappel si le pipeline ne tourne pas ce jour précis."""
    if is_weekend() and not force:
        print("[notifier] Week-end : pas de rappel.")
        return 0

    today = datetime.now(UTC).date()
    envoyes = 0

    with session_scope() as db:
        matches = (
            db.query(CompanyTender)
            .filter(
                CompanyTender.decision == "retenu",
                CompanyTender.commercial_id.isnot(None),
                CompanyTender.statut.notin_(["gagne", "perdu", "sans_suite"]),
                or_(CompanyTender.feedback.is_(None),
                    CompanyTender.feedback != "pas_pertinent"),
            )
            .all()
        )

        tender_ids = {m.tender_id for m in matches}
        commercial_ids = {m.commercial_id for m in matches}

        tenders = {
            t.id: t
            for t in db.query(Sotradies).filter(Sotradies.id.in_(tender_ids)).all()
        }
        commerciaux = {
            c.id: c
            for c in db.query(Commercial)
            .filter(
                Commercial.id.in_(commercial_ids),
                Commercial.actif.is_(True),
            )
            .all()
        }

        for match in matches:
            tender = tenders.get(match.tender_id)
            if tender is None or tender.date_limite is None:
                continue

            commercial = commerciaux.get(match.commercial_id)
            if commercial is None or commercial.company_id != match.company_id:
                continue

            jours = (tender.date_limite.date() - today).days

            # J-3 : fenêtre 1 à 3 jours avant (tolérante)
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
                    match.rappel_j3_envoye = datetime.now(UTC).replace(tzinfo=None)
                    envoyes += 1
                    print(f"[notifier] ✅ Rappel J-{jours} → {commercial.nom}")

            # J-1 : fenêtre exacte 1 jour (la fenêtre J-3 couvre déjà 1-3)
            # Le rappel J-1 est distinct et complémentaire
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
                    match.rappel_j1_envoye = datetime.now(UTC).replace(tzinfo=None)
                    envoyes += 1
                    print(f"[notifier] ✅ Rappel J-1 urgent → {commercial.nom}")

    print(f"[notifier] {envoyes} rappel(s) envoyé(s)")
    return envoyes