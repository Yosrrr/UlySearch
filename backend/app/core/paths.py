from pathlib import Path

# backend/app/core/paths.py → parents[1] = backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(
    __import__("os").environ.get("DATA_DIR", str(BACKEND_ROOT / "data"))
)
RAW_DUMP_DIR = DATA_DIR / "raw_scrapes"
DEBUG_DETAIL_DIR = DATA_DIR / "debug_detail"
BUYERS_TEMPLATE = DATA_DIR / "clients_sotradies_modele.xlsx"

for d in (RAW_DUMP_DIR, DEBUG_DETAIL_DIR, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)