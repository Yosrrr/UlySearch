"""
Lancement manuel du pipeline en ligne de commande.
python -m scripts.run_pipeline_all
python -m scripts.run_pipeline_all 2026-07-29
"""
import sys
from datetime import datetime

from app.services.pipeline import run_pipeline

if __name__ == "__main__":
    target = None
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    run_pipeline(target)