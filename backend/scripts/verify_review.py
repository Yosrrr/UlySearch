r"""
Vérifie (LECTURE SEULE) les corrections du rapport de revue technique.
Usage (depuis backend) : python scripts\verify_review.py
Ce sont des contrôles automatiques : OK = la correction est présente dans le code,
pas une preuve qu'elle marche en production (F-002/F-003/F-010 : à confirmer sur Render).
"""
import importlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

B = Path(__file__).resolve().parents[1]      # backend
R = B.parent                                 # racine du dépôt
sys.path.insert(0, str(B))
results = []


def read(rel, base=B):
    p = base / rel
    return p.read_text(encoding="utf-8-sig", errors="replace") if p.exists() else None


def res(fid, status, msg):
    results.append((fid, status, msg))


def body(src, name):
    """Corps d'une fonction (jusqu'à la prochaine ligne non indentée)."""
    if not src:
        return ""
    m = re.search(rf"^(?:async\s+)?def {name}\b.*?(?=^[^\s#]|\Z)", src, re.S | re.M)
    return m.group(0) if m else ""


docker = read("Dockerfile", R) or ""
render = read("render.yaml", R) or ""
reqs = read("requirements.txt") or ""

# F-001
in_reqs = re.search(r"^\s*reportlab\b", reqs, re.I | re.M)
installed = importlib.util.find_spec("reportlab") is not None
res("F-001", "OK" if in_reqs and installed else "KO",
    f"reportlab dans requirements.txt={bool(in_reqs)}, installé={installed}")

# F-002
pre = next((l for l in render.splitlines() if "preDeployCommand" in l), "")
workdirs = re.findall(r"^\s*WORKDIR\s+(\S+)", docker, re.M)
ok2 = "cd /app/backend" in pre or "backend/alembic.ini" in pre or (workdirs and workdirs[-1].rstrip("/") == "/app/backend")
res("F-002", "OK" if ok2 else "KO", f"preDeployCommand={pre.strip()[:90]!r} | WORKDIR={workdirs[-1:] }")

# F-003
n_key = render.count("SOURCE_CREDENTIALS_KEY")
n_group = render.count("fromGroup")
ok3 = n_key >= 3 or (n_key >= 1 and n_group >= 3)
res("F-003", "OK" if ok3 else "KO", f"SOURCE_CREDENTIALS_KEY x{n_key}, fromGroup x{n_group} (3 services attendus)")

# F-004 (exécuté depuis un autre dossier, comme dans le conteneur)
cwd = os.getcwd()
try:
    os.chdir(tempfile.mkdtemp())
    import app.core.templates as t
    importlib.reload(t)
    names = t.jinja_env.list_templates()
    for n in names:
        t.jinja_env.get_template(n)
    res("F-004", "OK" if names else "KO", f"{len(names)} template(s) chargé(s) hors du dossier backend")
except Exception as exc:
    res("F-004", "KO", f"{type(exc).__name__}: {exc}")
finally:
    os.chdir(cwd)

# F-005 (protection SSRF au moment de la requête)
svc = "\n".join((p.read_text(encoding="utf-8", errors="replace"))
                for p in (B / "app" / "services").rglob("*.py"))
resolves = "getaddrinfo" in svc or "gethostbyname" in svc
blocks = "is_private" in svc or "is_loopback" in svc or "is_link_local" in svc
res("F-005", "OK" if resolves and blocks else "KO",
    f"résolution DNS={resolves}, blocage IP privées={blocks} (vérifier aussi chaque redirection)")

# F-006
pipe = read("app/services/pipeline.py") or ""
uni_call = re.search(r"UniversalScraper\((.*?)\)", pipe, re.S)
res("F-006", "OK" if uni_call and "auth" in uni_call.group(1) else "KO",
    "auth transmis à UniversalScraper" if uni_call and "auth" in uni_call.group(1) else "auth non transmis")

# F-007
adm = read("app/api/admin_sources.py") or ""
upd = body(adm, "update_source")
res("F-007", "OK" if "superadmin" in upd else "KO",
    "contrôle superadmin dans update_source" if "superadmin" in upd else "aucun contrôle superadmin dans update_source")

# F-008 (le modèle est-il appelé sans catégories ?)
try:
    import app.services.ai_filter_and_extract as m
    calls, orig = [], m.call_local_llm_json
    m.call_local_llm_json = lambda *a, **k: (calls.append(1) or {
        "pertinent": False, "categorie": None, "score": 0, "raison": "ok", "description": "x"})
    try:
        m.filter_and_extract("Objet : Acquisition de climatiseurs\nAcheteur : STEG", {})
    finally:
        m.call_local_llm_json = orig
    res("F-008", "OK" if calls else "KO", f"appels au modèle sans catégories : {len(calls)}")
except Exception as exc:
    res("F-008", "??", f"{type(exc).__name__}: {exc}")

# F-010
tag = re.search(r"playwright/python:v([\d.]+)", docker)
pin = re.search(r"^\s*playwright==([\d.]+)", reqs, re.M)
same = tag and pin and tag.group(1) == pin.group(1)
res("F-010", "OK" if same or "playwright install" in docker else "KO",
    f"image={tag.group(1) if tag else '?'} paquet={pin.group(1) if pin else '?'}")

# F-011 (le changement des mots de passe ne peut pas être vérifié par script)
try:
    files = subprocess.run(["git", "ls-files"], cwd=R, capture_output=True, text=True).stdout.splitlines()
    envs = [f for f in files if re.search(r"(^|/)\.env($|\.)", f) and not f.endswith(".example")]
    res("F-011", "OK" if not envs else "KO", f".env suivis par git : {envs or 'aucun'} (+ mot de passe SMTP changé ?)")
except Exception as exc:
    res("F-011", "??", str(exc))

# F-013
res("F-013", "KO" if re.search(r"forwarded-allow-ips[= ]+['\"]?\*", docker) else "OK",
    "forwarded-allow-ips='*' encore présent" if "forwarded-allow-ips" in docker and "*" in docker else "pas de confiance à tous les proxys")

# F-016
users = read("app/api/admin_users.py") or ""
vp = re.search(r"VALID_PROFILES\s*=\s*\(([^)]*)\)", users)
has_com = bool(vp and "commercial" in vp.group(1))
has_cid = "company_id" in (re.search(r"class UserCreate.*?(?=^class |\Z)", users, re.S | re.M) or [""])[0]
res("F-016", "OK" if has_com and has_cid else "KO", f"profil commercial={has_com}, company_id à la création={has_cid}")

# F-017
ten = read("app/api/tenders.py") or ""
upd_t = body(ten, "update_tender_status") or body(ten, "update_tender")
res("F-017", "OK" if '"retenu"' in upd_t else "KO", "statut 'retenu' géré" if '"retenu"' in upd_t else "statut 'retenu' refusé")

# F-018
notif = read("app/services/notifier.py") or ""
dig = body(notif, "send_daily_digest")
cut = re.search(r"cutoff\s*=.*?timedelta\(([^)]*)\)", dig)
val = cut.group(1) if cut else "?"
res("F-018", "OK" if cut and ("days" in val) else "~~", f"fenêtre du résumé : timedelta({val}) (24 h = week-end perdu le lundi)")

# F-021
tun = read("app/services/scrapers/tuneps_scraper.py") or ""
res("F-021", "KO" if "verify=False" in tun else "OK", "verify=False présent" if "verify=False" in tun else "vérification TLS active")

# F-022
tasks = read("app/workers/tasks.py") or ""
tl = "time_limit" in tasks
lk = bool(re.search(r"\.lock\(|redis_lock|SETNX|nx=True", tasks, re.I))
res("F-022", "OK" if tl and lk else "KO", f"limite de temps={tl}, verrou={lk}")

# F-023
main = read("app/main.py") or ""
res("F-023", "OK" if ("/ready" in main or "SELECT 1" in main) else "KO",
    "contrôle santé avec base/Redis" if ("/ready" in main or "SELECT 1" in main) else "/health statique")
res("F-023b", "~~", f"print() restants dans app : {svc.count('print(') + main.count('print(')}")

# F-024
wf = list((R / ".github" / "workflows").glob("*.y*ml")) if (R / ".github").exists() else []
res("F-024", "OK" if wf else "KO", f"workflows CI : {[w.name for w in wf] or 'aucun'}")

# F-025
res("F-025", "OK" if "docs_url" in main else "KO", "docs_url configuré" if "docs_url" in main else "Swagger public")

# F-027
rem = read("app/services/buyer_rematcher.py") or ""
leak = re.search(r"\b(tender|t|s|sotradies)\.acheteur_connu\s*=", rem)
res("F-027", "KO" if leak else "OK", "écriture dans sotradies" if leak else "écriture uniquement dans company_tenders")

# F-029
boot = read("scripts/bootstrap.py") or ""
mig = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (B / "alembic" / "versions").glob("*.py"))
seed = re.search(r"marchespublics|tuneps\.tn", boot + mig, re.I)
res("F-029", "OK" if seed else "KO", "ONMP/TUNEPS créés au démarrage" if seed else "sources dédiées non créées")

# F-030
user_line = re.findall(r"^\s*USER\s+(\S+)", docker, re.M)
uni = read("app/services/scrapers/universal_scraper.py") or ""
ok30 = user_line and user_line[-1] not in ("root", "0") and "--no-sandbox" not in uni
res("F-030", "OK" if ok30 else "KO", f"USER={user_line[-1:] or 'root'}, --no-sandbox={'--no-sandbox' in uni}")

print(f"{'Point':<7} {'État':<5} Détail")
for fid, status, msg in results:
    print(f"{fid:<7} {status:<5} {msg}")
ko = [f for f, s, _ in results if s == "KO"]
print(f"\nKO : {len(ko)} -> {', '.join(ko) or 'aucun'}")
print("Rappel : F-002, F-003, F-010 doivent être confirmés sur un déploiement Render de test.")