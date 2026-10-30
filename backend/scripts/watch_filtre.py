"""
Vérification du filtre EN DIRECT, sur les vraies offres et la vraie IA — sans CSV.

Population : les offres déjà soumises à ce client par le pipeline (company_tenders),
les plus récentes d'abord. Chaque ligne montre la décision du filtre tel qu'il est
maintenant ; '*' signale une différence avec la décision actuellement en base.

Pré-requis : Ollama démarré, LLM_ENABLED=true (.env local ou $env:LLM_ENABLED).

  python -m scripts.watch_filtre --company-id 4 --rejouer 40                        # lecture seule
  python -m scripts.watch_filtre --company-id 4 --rejouer 700 --contient "محولات"   # une offre précise
  python -m scripts.watch_filtre --company-id 2 --rejouer 300 --appliquer           # écrit -> visible dans l'app
  python -m scripts.watch_filtre --company-id 4 --suivre                            # tail du pipeline (Ctrl+C)
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.database import session_scope
from app.models.company_tender import CompanyTender
from app.models.configuration import Configuration
from app.models.sotradies import Sotradies
from app.services import scoring_orchestrator as orch
from app.services.pipeline import _best_category, _resolve_commercial_id, _tender_to_raw
from app.services.pipeline_logger import log_pipeline_event

SEUIL_DECISION_DEFAUT = 50
SEUIL_ALERTE_DEFAUT = 70
METHODES_EN_ATTENTE = ("a_verifier", "a_examiner")


def _court(value, maxi: int) -> str:
    texte = " ".join(str(value or "").split())
    return texte if len(texte) <= maxi else texte[: maxi - 1] + "…"


def _detail_principal(score_details: dict, score: int) -> dict:
    """Détail de la catégorie qui porte le score ; pour un rejet, celui qui porte la raison."""
    details = [d for d in (score_details or {}).values() if isinstance(d, dict)]
    if score > 0:
        for d in details:
            if int(d.get("score", 0) or 0) == score:
                return d
    for d in details:
        if d.get("raison_ia") or d.get("categorie_ia") or d.get("mot_exclusion"):
            return d
    return details[0] if details else {}


def _decision_pipeline(score_details: dict, score: int, seuil: int) -> str:
    """Même règle que pipeline._score_company_tender : IA indisponible -> a_verifier."""
    if any(isinstance(d, dict) and d.get("methode") == "a_verifier" for d in (score_details or {}).values()):
        return "a_verifier"
    return "retenu" if score >= seuil else "rejete"


def _etiquette(score: int, methode: str, seuil: int, alerte: int) -> str:
    if score >= alerte:
        return "RETENU !"
    if score >= seuil:
        return "RETENU"
    return "à vérif." if methode in METHODES_EN_ATTENTE else "rejeté"


def _ligne(source, objet, preuve, score, methode, confiance, raison, seuil, alerte) -> str:
    return (f"{datetime.now():%H:%M:%S} | {str(source or '')[:7]:7} | {_court(objet, 55):55} | {preuve:7} | "
            f"{_etiquette(score, methode, seuil, alerte):8} {score:>3} | {str(methode or '-')[:12]:12} | "
            f"{str(confiance or '-')[:7]:7} | {_court(raison, 100)}")


def _config(db, company_id: int) -> Configuration:
    config = db.execute(select(Configuration).where(Configuration.company_id == company_id)).scalar_one_or_none()
    if config is None or not config.categories:
        ids = [c.company_id for c in db.execute(select(Configuration)).scalars()]
        raise SystemExit(f"Aucune catégorie configurée pour company_id={company_id}. Configurés : {ids}")
    return config


def _lignes_client(db, company_id: int, limite: int, source: str | None, contient: str | None = None):
    query = (select(CompanyTender, Sotradies)
             .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
             .where(CompanyTender.company_id == company_id))
    if source:
        query = query.where(Sotradies.source == source)
    if contient:
        query = query.where(Sotradies.objet.ilike(f"%{contient}%"))
    return db.execute(query.order_by(Sotradies.date_detection.desc()).limit(limite)).all()


def rejouer(args) -> None:
    if not getattr(settings, "LLM_ENABLED", False):
        raise SystemExit('LLM_ENABLED=false : l\'IA ne serait pas appelée. $env:LLM_ENABLED = "true" puis relance.')
    orch.reset_cache()
    compteurs: Counter = Counter()
    run_id = uuid4().hex

    with session_scope() as db:
        config = _config(db, args.company_id)
        categories = config.categories or {}
        exclusions = config.exclusion_keywords or []
        profil = getattr(config, "description_activite", None)
        seuil = config.score_decision_threshold or SEUIL_DECISION_DEFAUT
        alerte = config.score_instant_alert_threshold or SEUIL_ALERTE_DEFAUT
        lignes = _lignes_client(db, args.company_id, args.rejouer, args.source, args.contient)
        if args.groupe:
            def _a_mot_cle(offre):
                texte = f"{offre.objet or ''} {offre.categorie or ''} {offre.description_detaillee or ''}"
                return any(orch._indices(texte, categories).values())
            lignes = [(ct, o) for ct, o in lignes if _a_mot_cle(o) == (args.groupe == "avec")]

        print(f"company_id={args.company_id} | seuil={seuil} | alerte={alerte} | modèle={settings.OLLAMA_MODEL}"
              f" | fiche={'oui' if (profil or '').strip() else 'NON'} | {len(lignes)} offre(s)"
              f"{f' contenant « {args.contient} »' if args.contient else ''}"
              f" | {'ÉCRITURE en base' if args.appliquer else 'lecture seule'}\n")
        print(f" {'heure':8} | {'src':7} | {'objet':55} | {'preuve':7} | {'décision':12} | {'méthode':12} | {'conf.':7} | raison")
        print("-" * 170)

        for i, (ct, offre) in enumerate(lignes, start=1):
            avant = f"{ct.decision} {int(ct.score or 0)}"
            texte = f"{offre.objet or ''} {offre.categorie or ''} {offre.description_detaillee or ''}"
            preuve = "mot-clé" if any(orch._indices(texte, categories).values()) else "aucun"
            t0 = time.perf_counter()
            try:
                details = orch.score_tender_full(_tender_to_raw(offre), categories, exclusions, profil_client=profil) or {}
            except Exception as exc:
                print(f" {datetime.now():%H:%M:%S} | ERREUR {type(exc).__name__}: {_court(exc, 80)} | {_court(offre.objet, 60)}", flush=True)
                compteurs["erreur"] += 1
                continue
            duree = time.perf_counter() - t0

            categorie, score = _best_category(details)
            d = _detail_principal(details, score)
            methode = str(d.get("methode") or "-")
            raison = d.get("raison_ia") or d.get("raison") or d.get("mot_exclusion") or ""
            if d.get("preuve"):
                raison = f"[{d['preuve']}] {raison}"
            decision = _decision_pipeline(details, score, seuil)
            change = decision != ct.decision or int(score) != int(ct.score or 0)
            compteurs[_etiquette(score, methode, seuil, alerte)] += 1
            compteurs["changements"] += int(change)
            print(("*" if change else " ") + _ligne(offre.source, offre.objet, preuve, score, methode,
                  d.get("confiance_ia"), raison, seuil, alerte)
                  + f" ({duree:.1f}s{f', avant : {avant}' if change else ''})", flush=True)

            if not args.appliquer:
                continue
            if ct.statut != "nouveau" or getattr(ct, "feedback", None):
                compteurs["non écrit (traité par un commercial)"] += 1
                continue
            ct.score, ct.categorie, ct.score_details, ct.decision = score, categorie, details, decision
            ct.commercial_id = _resolve_commercial_id(db, args.company_id, categorie, config.assignment_rules or {}, categories)
            log_pipeline_event(db, run_id, "RESCORED", source=offre.source, tender_id=offre.id,
                               payload={"company_id": args.company_id, "avant": avant, "score": score,
                                        "decision": decision, "methode": methode})
            compteurs["écrit"] += 1
            if i % 10 == 0:
                db.commit()      # un Ctrl+C ne perd pas ce qui précède

    print("\nRésumé :", ", ".join(f"{k}={v}" for k, v in sorted(compteurs.items())))
    print("Stats orchestrateur :", orch.get_scoring_stats())
    if args.appliquer:
        print("Écrit en base : ouvre l'application (offres retenues / rejetées) pour vérifier.")


def suivre(args) -> None:
    print(f"Suivi en direct des décisions écrites pour company_id={args.company_id} (Ctrl+C pour arrêter).")
    print(f'Autre terminal : python -c "from app.services.pipeline import run_pipeline; print(run_pipeline(company_id={args.company_id}))"\n')
    vus: dict[int, tuple] = {}
    premier = True
    try:
        while True:
            with session_scope() as db:
                config = _config(db, args.company_id)
                seuil = config.score_decision_threshold or SEUIL_DECISION_DEFAUT
                alerte = config.score_instant_alert_threshold or SEUIL_ALERTE_DEFAUT
                rows = db.execute(select(CompanyTender, Sotradies)
                                  .join(Sotradies, Sotradies.id == CompanyTender.tender_id)
                                  .where(CompanyTender.company_id == args.company_id)
                                  .order_by(CompanyTender.id.desc()).limit(3000)).all()
                instantane = [(ct.id, int(ct.score or 0), ct.decision, dict(ct.score_details or {}), s.source, s.objet)
                              for ct, s in rows]
            for ct_id, score, decision, details, source, objet in reversed(instantane):
                d = _detail_principal(details, score)
                methode = str(d.get("methode") or "-")
                signature = (score, decision, methode)
                precedent = vus.get(ct_id)
                if precedent == signature:
                    continue
                vus[ct_id] = signature
                if premier:
                    continue
                raison = d.get("raison_ia") or d.get("raison") or d.get("mot_exclusion") or ""
                preuve = "mot-clé" if d.get("mots_cles_matches") or d.get("mot_cle_present") else "-"
                suffixe = "" if precedent is None else f" (avant : {precedent[1]} {precedent[0]})"
                print(("+" if precedent is None else "~") + _ligne(source, objet, preuve, score, methode,
                      d.get("confiance_ia"), raison, seuil, alerte) + suffixe, flush=True)
            if premier:
                print(f"{len(vus)} décision(s) déjà en base : seules les nouvelles ou modifiées s'afficheront.\n", flush=True)
                premier = False
            time.sleep(args.intervalle)
    except KeyboardInterrupt:
        print("\nArrêt du suivi.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--rejouer", type=int, default=0, metavar="N", help="rejoue les N dernières offres du client")
    parser.add_argument("--appliquer", action="store_true", help="avec --rejouer : écrit le résultat dans company_tenders")
    parser.add_argument("--suivre", action="store_true", help="affiche en continu ce que le pipeline écrit")
    parser.add_argument("--source", default=None, help="limiter à une source : onmp, tuneps, web_12…")
    parser.add_argument("--contient", default=None, help="ne rejoue que les objets contenant ce texte (ex. محولات)")
    parser.add_argument("--intervalle", type=float, default=2.0, help="secondes entre deux lectures (--suivre)")
    parser.add_argument("--groupe", choices=("avec", "sans"), default=None,
                    help="ne garder que les offres avec / sans mot-clé du client")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.suivre:
        suivre(args)
    elif args.rejouer > 0:
        rejouer(args)
    else:
        parser.error("indique --rejouer N (avec ou sans --appliquer) ou --suivre")


if __name__ == "__main__":
    main()
