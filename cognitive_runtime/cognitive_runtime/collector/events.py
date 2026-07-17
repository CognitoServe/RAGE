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
        source="result_collector",
        timestamp=_utc_now_iso(),
        payload=payload,
    )


def create_result_collected_event(
    action_id: str, success: bool, duration_ms: float
) -> Event:
    return _create_event(
        "ResultCollected",
        {"action_id": action_id, "success": success, "duration_ms": duration_ms},
    )


def create_observation_created_event(
    observation_id: str, action_id: str, plan_id: str | None
) -> Event:
    return _create_event(
        "ObservationCreated",
        {"observation_id": observation_id, "action_id": action_id, "plan_id": plan_id},
    )


def create_statistics_updated_event(total: int, success_rate: float) -> Event:
    return _create_event(
        "StatisticsUpdated",
        {"total_executions": total, "success_rate": success_rate},
    )


def create_execution_recorded_event(observation_id: str) -> Event:
    return _create_event(
        "ExecutionRecorded",
        {"observation_id": observation_id},
    )


def create_collector_cleared_event() -> Event:
    return _create_event("CollectorCleared", {})
