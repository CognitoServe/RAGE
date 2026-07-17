"""
Action Events — RFC-0011

Factory functions for all Action lifecycle events.

Design: Events are pure data (frozen `Event` instances from the events module).
Each factory function takes only the minimal data required to describe *what
happened* — no business logic, no state access, no side effects.

Event Types
-----------
ActionCreated   — A new action has been produced by a planner step.
ActionQueued    — An action has been accepted into the execution queue.
ActionStarted   — An executor has begun processing the action.
ActionCompleted — An executor has successfully finished the action.
ActionFailed    — An executor has failed to complete the action.
ActionCancelled — An action was cancelled before or during execution.
"""

from cognitive_runtime.events.models import Event

from .models import Action


def create_action_created_event(action: Action) -> Event:
    """Emitted when a new Action is created from a plan step."""
    return Event(
        event_type="ActionCreated",
        source="ActionModel",
        payload={
            "action_id": action.action_id,
            "plan_id": action.plan_id,
            "step_id": action.step_id,
            "type": action.type,
            "target": action.target,
            "priority": action.priority,
            "status": action.status,
        },
    )


def create_action_queued_event(action_id: str) -> Event:
    """Emitted when an Action is placed into the execution queue."""
    return Event(
        event_type="ActionQueued",
        source="ActionModel",
        payload={"action_id": action_id},
    )


def create_action_started_event(action_id: str) -> Event:
    """Emitted when an executor begins processing an Action."""
    return Event(
        event_type="ActionStarted",
        source="ActionModel",
        payload={"action_id": action_id},
    )


def create_action_completed_event(action_id: str) -> Event:
    """Emitted when an executor successfully finishes an Action."""
    return Event(
        event_type="ActionCompleted",
        source="ActionModel",
        payload={"action_id": action_id},
    )


def create_action_failed_event(action_id: str, reason: str) -> Event:
    """Emitted when an executor fails to complete an Action."""
    return Event(
        event_type="ActionFailed",
        source="ActionModel",
        payload={"action_id": action_id, "reason": reason},
    )


def create_action_cancelled_event(action_id: str) -> Event:
    """Emitted when an Action is cancelled before or during execution."""
    return Event(
        event_type="ActionCancelled",
        source="ActionModel",
        payload={"action_id": action_id},
    )
