import uuid
from typing import Any

from cognitive_runtime.events.models import Event


def create_decision_created_event(
    decision_id: str,
    payload: dict[str, Any] | None = None,
    source: str = "DecisionEngine",
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="DecisionCreated",
        source=source,
        payload={"decision_id": decision_id, **(payload or {})},
    )


def create_decision_explained_event(decision_id: str, explanation: str) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="DecisionExplained",
        source="DecisionEngine",
        payload={"decision_id": decision_id, "explanation": explanation},
    )


def create_decision_rejected_event(decision_id: str, reason: str) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type="DecisionRejected",
        source="DecisionEngine",
        payload={"decision_id": decision_id, "reason": reason},
    )
