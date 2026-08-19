# app/services/local_llm_client.py
"""
Client partagé pour appeler le modèle local Qwen2.5 3B via Ollama.

⚠️ Un modèle 3B en local est nettement moins fiable qu'un modèle cloud
pour produire du JSON strict — cette couche prévoit donc une extraction
tolérante (recherche du bloc JSON même si le modèle ajoute du texte
autour, malgré la consigne), avec échec propre sinon.
"""
import json
import re

try:
    import ollama
except ImportError:  # pragma: no cover - dépendance optionnelle si Ollama n'est pas installé
    ollama = None

from app.core.config import settings

_client = ollama.Client(host=settings.OLLAMA_HOST) if ollama is not None else None


def call_local_llm_json(system_prompt: str, user_prompt: str) -> dict | None:
    """Appelle Qwen en local, retourne un dict si le JSON est extractible,
    None sinon (l'appelant décide alors du comportement par défaut)."""
    if _client is None:
        print("[local_llm_client] Ollama n'est pas installé. Le mode local est désactivé.")
        return None
    try:
        response = _client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format="json",   
            options={"temperature": 0},
        )
        raw_text = response["message"]["content"].strip()
        return _extract_json(raw_text)
    except Exception as e:
        print(f"[local_llm_client] Échec de l'appel Ollama : {e}")
        return None


def _extract_json(text: str) -> dict | None:
    # Cas idéal : le modèle a bien répondu uniquement en JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Cas fréquent avec un petit modèle : du texte autour, ou des ```json ... ```
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    print(f"[local_llm_client] Impossible d'extraire du JSON valide. Réponse brute : {text[:200]}")
    return None