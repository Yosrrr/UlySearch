r"""
Répare app/api/tenders.py (simulation par défaut) :
 1. list_tenders : retire le bloc de repêchage collé par erreur
    (tender_id / payload non définis -> erreur 500 pour tout client sur "Marchés").
 2. update_tender_status : version complète et cohérente.
Usage : python scripts\fix_tenders.py            (simulation)
        python scripts\fix_tenders.py --apply    (écrit, copie tenders.py.bak)
"""
import ast
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "api" / "tenders.py"
raw = p.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
src = raw.decode("utf-8-sig")
tree = ast.parse(src)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
lines = src.splitlines(keepends=True)


def params(fn):
    return {a.arg for a in fn.args.args + fn.args.kwonlyargs}


def find_call(fn, name):
    return next((n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == name), None)


edits = []  # (début 0-indexé, fin exclusive, nouveau texte)

# ---- 1. list_tenders ----
lt, ex = funcs["list_tenders"], funcs["export_tenders"]
used = {n.id for n in ast.walk(lt) if isinstance(n, ast.Name)}
broken = bool({"tender_id", "payload"} & used)
print(f"[1] list_tenders utilise tender_id/payload (bug) : {broken}")
if broken:
    c_client = find_call(ex, "_filtered_for_client")
    c_super = find_call(ex, "_filtered_for_superadmin")
    if not (c_client and c_super):
        sys.exit("Appels introuvables dans export_tenders : arrêt, envoie-moi ce message.")
    missing = ({n.id for n in ast.walk(c_client) if isinstance(n, ast.Name)}
               | {n.id for n in ast.walk(c_super) if isinstance(n, ast.Name)}) \
        - params(lt) - {"_filtered_for_client", "_filtered_for_superadmin", "company_id"}
    if missing:
        sys.exit(f"Paramètres absents de list_tenders : {missing} : arrêt.")
    body = (
        "    if _is_superadmin(user):\n"
        f"        return {ast.unparse(c_super)}\n\n"
        "    company_id = _require_company_id(user)\n"
        f"    return {ast.unparse(c_client)}\n"
    )
    edits.append((lt.body[0].lineno - 1, lt.end_lineno, body))
    print("    -> corps remplacé par :\n" + body)

# ---- 2. update_tender_status ----
NEW_UT = '''def update_tender_status(
    tender_id: str,
    payload: TenderStatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    now = datetime.now(UTC).replace(tzinfo=None)

    # Superadmin : vue brute Sotradies (comportement inchangé)
    if _is_superadmin(user):
        if payload.statut not in SUPERADMIN_STATUTS:
            raise HTTPException(status_code=400, detail="Statut invalide.")
        t = db.query(Sotradies).filter_by(id=tender_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Marché introuvable")
        ancien = t.statut
        t.statut = payload.statut
        t.date_derniere_action = now
        db.add(AuditLog(
            sotradies_id=t.id,
            utilisateur_email=user.get("sub", "inconnu"),
            action="changement_statut",
            detail=f"{ancien} -> {payload.statut}",
        ))
        db.commit()
        db.refresh(t)
        return to_tender_out_from_sotradies(t)

    # Client
    company_id = _require_company_id(user)
    match = (
        db.query(CompanyTender)
        .filter_by(company_id=company_id, tender_id=tender_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Marché introuvable")

    if payload.statut == "retenu":
        # Repêchage = décision humaine : change la DÉCISION.
        # feedback="pertinent" protège l'offre contre les recalculs automatiques.
        ancien = match.decision
        match.decision = "retenu"
        match.feedback = "pertinent"
        match.feedback_at = now
        if match.statut in (None, "sans_suite"):
            match.statut = "nouveau"  # reprend le cycle commercial
        details = dict(match.score_details or {})
        details["_repechage"] = {"date": now.isoformat(timespec="seconds"),
                                 "par": user.get("sub"), "ancienne_decision": ancien}
        match.score_details = details
        action, detail = "repechage", f"{ancien} -> retenu"
    else:
        if payload.statut not in CLIENT_STATUTS:
            raise HTTPException(status_code=400, detail="Statut invalide.")
        ancien = match.statut
        match.statut = payload.statut
        action, detail = "changement_statut", f"{ancien} -> {payload.statut}"

    tender = db.query(Sotradies).filter_by(id=tender_id).first()
    if tender:
        tender.date_derniere_action = now

    db.add(AuditLog(
        sotradies_id=tender_id,
        utilisateur_email=user.get("sub", "inconnu"),
        action=action,
        detail=detail,
    ))
    db.commit()
    db.refresh(match)
    return to_tender_out_from_match(match, tender, _commercial_name(db, match.commercial_id))
'''
ut = funcs["update_tender_status"]
edits.append((ut.lineno - 1, ut.end_lineno, NEW_UT))  # décorateur @router.patch conservé
print("[2] update_tender_status : remplacé par la version complète")

# Appliquer du bas vers le haut (les numéros de ligne restent valides)
for start, end, text in sorted(edits, key=lambda e: e[0], reverse=True):
    lines[start:end] = [text]
new = "".join(lines)

compile(new, str(p), "exec")  # lève une erreur si le résultat est invalide
check = {n.name: n for n in ast.parse(new).body if isinstance(n, ast.FunctionDef)}
assert not ({"tender_id", "payload"} & {n.id for n in ast.walk(check["list_tenders"]) if isinstance(n, ast.Name)})
print("Contrôles : compilation OK, list_tenders propre.")

if "--apply" in sys.argv:
    p.with_suffix(".py.bak").write_bytes(raw)
    p.write_text(new, encoding="utf-8-sig" if bom else "utf-8", newline="")
    print("ÉCRIT (copie tenders.py.bak créée).")
else:
    print("SIMULATION : rien n'a été écrit. Relance avec --apply.")