import uuid

from cognitive_runtime.events.models import Event


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()

def create_http_request_started_event(
    action_id: str, action_type: str, url: str
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="HttpRequestStarted",
        source="http_adapter",
        timestamp=_utc_now_iso(),
        payload={"action_id": action_id, "action_type": action_type, "url": url},
    )

def create_http_request_completed_event(
    action_id: str, action_type: str, url: str, status_code: int, duration_ms: float
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="HttpRequestCompleted",
        source="http_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "url": url,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )

def create_http_request_failed_event(
    action_id: str, action_type: str, url: str, reason: str, duration_ms: float
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="HttpRequestFailed",
        source="http_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "url": url,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )

def create_http_validation_failed_event(
    action_id: str, action_type: str, url: str | None, reason: str
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="HttpValidationFailed",
        source="http_adapter",
        timestamp=_utc_now_iso(),
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "url": url,
            "reason": reason,
        },
    )
