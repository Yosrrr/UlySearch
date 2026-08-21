"""Service centralisé de logging pipeline."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.models.pipeline_log import PipelineLog


def _json_safe(value):
    """Convertit les objets courants en types JSON sérialisables."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return value


def log_pipeline_event(
    db,
    run_id: str,
    event_type: str,
    *,
    source: str | None = None,
    tender_id: str | None = None,
    message: str | None = None,
    payload: dict | None = None,
) -> None:
    """Ajoute un événement de pipeline dans la session courante.

    Ne commit pas : le commit est géré par session_scope().
    Ne doit jamais casser le pipeline si le logging échoue.
    """
    try:
        db.add(
            PipelineLog(
                run_id=run_id,
                event_type=event_type,
                source=source,
                tender_id=tender_id,
                message=message,
                payload=_json_safe(payload or {}),
            )
        )
    except Exception as exc:
        print(f"[pipeline_logger] ⚠️ Échec log {event_type}: {exc}")