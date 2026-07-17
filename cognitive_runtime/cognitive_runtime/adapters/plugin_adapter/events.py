import uuid
from datetime import UTC, datetime
from typing import Any

from cognitive_runtime.events.models import Event


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _create_event(event_type: str, payload: dict[str, Any]) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        source="plugin_adapter",
        timestamp=_utc_now_iso(),
        payload=payload,
    )


def create_plugin_execution_started_event(
    action_id: str, plugin_name: str, parameters: dict[str, Any]
) -> Event:
    return _create_event(
        "PluginExecutionStarted",
        {
            "action_id": action_id,
            "plugin_name": plugin_name,
            "parameters": parameters,
        },
    )


def create_plugin_execution_completed_event(
    action_id: str,
    plugin_name: str,
    plugin_version: str,
    duration_ms: float,
) -> Event:
    return _create_event(
        "PluginExecutionCompleted",
        {
            "action_id": action_id,
            "plugin_name": plugin_name,
            "plugin_version": plugin_version,
            "duration_ms": duration_ms,
        },
    )


def create_plugin_execution_failed_event(
    action_id: str, plugin_name: str, reason: str, duration_ms: float
) -> Event:
    return _create_event(
        "PluginExecutionFailed",
        {
            "action_id": action_id,
            "plugin_name": plugin_name,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )


def create_plugin_validation_failed_event(
    action_id: str, plugin_name: str | None, reason: str
) -> Event:
    return _create_event(
        "PluginValidationFailed",
        {
            "action_id": action_id,
            "plugin_name": plugin_name,
            "reason": reason,
        },
    )
