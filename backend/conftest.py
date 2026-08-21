import sys
from pathlib import Path

# Ajoute le dossier backend au PYTHONPATH pour que pytest puisse importer app.*
sys.path.insert(0, str(Path(__file__).parent))