"""Configuration pytest : rend 'app' importable depuis scripts/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))