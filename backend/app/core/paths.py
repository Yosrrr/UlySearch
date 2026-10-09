import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("DATA_DIR", BACKEND_ROOT / "data"))
RAW_DUMP_DIR = DATA_DIR / "raw_scrapes"
DEBUG_DETAIL_DIR = DATA_DIR / "debug_detail"
BUYERS_TEMPLATE = DATA_DIR / "clients_sotradies_modele.xlsx"

for _d in (DATA_DIR, RAW_DUMP_DIR, DEBUG_DETAIL_DIR):
    _d.mkdir(parents=True, exist_ok=True)