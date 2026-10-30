import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _llm_desactive_par_defaut(monkeypatch):
    """Aucun test ne doit appeler Ollama réellement, quelle que soit la variable d'environnement."""
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
