"""
Queue Events — RFC-0012

Factory functions for all Execution Queue lifecycle events.

These are scheduling-layer events, distinct from the action execution events
in `cognitive_runtime.actions.events`. They describe *queue* state changes
(entered queue, left queue, queue cleared) rather than execution outcomes.

Event Types
-----------
ActionEnqueued      — An action was accepted into the pending bucket.
ActionDequeued      — An action was dispatched to a consumer (now RUNNING).
ActionRetried       — A failed action was re-enqueued for another attempt.
ActionQueueCleared  — The pending bucket was emptied.
"""

from cognitive_runtime.events.models import Event


def create_action_enqueued_event(action_id: str, priority: int, sequence: int) -> Event:
    """Emitted when an action enters the pending bucket."""
    return Event(
        event_type="ActionEnqueued",
        source="ExecutionQueue",
        payload={
            "action_id": action_id,
            "priority": priority,
            "sequence": sequence,
        },
    )


def create_action_dequeued_event(action_id: str, priority: int) -> Event:
    """Emitted when an action is removed from pending and handed to a consumer."""
    return Event(
        event_type="ActionDequeued",
        source="ExecutionQueue",
        payload={
            "action_id": action_id,
            "priority": priority,
        },
    )


def create_action_retried_event(action_id: str, attempt: int) -> Event:
    """Emitted when a failed action is re-enqueued for retry."""
    return Event(
        event_type="ActionRetried",
        source="ExecutionQueue",
        payload={
            "action_id": action_id,
            "attempt": attempt,
        },
    )


def create_queue_cleared_event(cleared_count: int) -> Event:
    """Emitted when the pending bucket is emptied via clear()."""
    return Event(
        event_type="ActionQueueCleared",
        source="ExecutionQueue",
        payload={"cleared_count": cleared_count},
    )
