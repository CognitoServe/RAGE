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
        source="process_adapter",
        timestamp=_utc_now_iso(),
        payload=payload,
    )


def create_process_started_event(
    action_id: str, action_type: str, target: str, args: list[str]
) -> Event:
    return _create_event(
        "ProcessStarted",
        {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "args": args,
        },
    )


def create_process_completed_event(
    action_id: str, action_type: str, target: str, exit_code: int, duration_ms: float
) -> Event:
    return _create_event(
        "ProcessCompleted",
        {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
    )


def create_process_failed_event(
    action_id: str, action_type: str, target: str, reason: str, duration_ms: float
) -> Event:
    return _create_event(
        "ProcessFailed",
        {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )


def create_process_validation_failed_event(
    action_id: str, action_type: str, target: str | None, reason: str
) -> Event:
    return _create_event(
        "ProcessValidationFailed",
        {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "reason": reason,
        },
    )
