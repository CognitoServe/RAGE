import uuid

from cognitive_runtime.events.models import Event


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def create_filesystem_operation_started_event(
    action_id: str, action_type: str, target: str
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="FilesystemOperationStarted",
        source="filesystem_adapter",
        timestamp=_utc_now_iso(),
        payload={"action_id": action_id, "action_type": action_type, "target": target},
    )


def create_filesystem_operation_completed_event(
    action_id: str, action_type: str, target: str, duration_ms: float
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="FilesystemOperationCompleted",
        source="filesystem_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "duration_ms": duration_ms,
        },
    )


def create_filesystem_operation_failed_event(
    action_id: str, action_type: str, target: str, reason: str, duration_ms: float
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="FilesystemOperationFailed",
        source="filesystem_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )


def create_filesystem_validation_failed_event(
    action_id: str, action_type: str, target: str | None, reason: str
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="FilesystemValidationFailed",
        source="filesystem_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "reason": reason,
        },
    )
