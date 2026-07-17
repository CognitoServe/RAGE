"""
Executor Events — RFC-0013

Factory functions for all Executor lifecycle events.

These are orchestration-layer events. They describe *executor* and *dispatch*
state changes — not adapter implementation outcomes, not queue scheduling
events. Each module in the cognitive runtime publishes events from its own
source string.

Event Types
-----------
ExecutorStarted             — The executor entered running state.
ExecutorStopped             — The executor exited running state.
ActionExecutionStarted      — The executor began dispatching an action.
ActionExecutionCompleted    — The adapter returned successfully.
ActionExecutionFailed       — The adapter raised or the dispatch was rejected.
AdapterResolutionFailed     — No adapter found for the given ActionType.
UnsupportedActionType       — The action type is not registered in this executor.
"""

from cognitive_runtime.events.models import Event


def create_executor_started_event() -> Event:
    """Emitted when start() is called on a stopped executor."""
    return Event(
        event_type="ExecutorStarted",
        source="Executor",
        payload={},
    )


def create_executor_stopped_event() -> Event:
    """Emitted when stop() is called on a running executor."""
    return Event(
        event_type="ExecutorStopped",
        source="Executor",
        payload={},
    )


def create_action_execution_started_event(action_id: str, action_type: str) -> Event:
    """Emitted immediately before the adapter's execute() is called."""
    return Event(
        event_type="ActionExecutionStarted",
        source="Executor",
        payload={
            "action_id": action_id,
            "action_type": action_type,
        },
    )


def create_action_execution_completed_event(
    action_id: str, action_type: str, duration_ms: float
) -> Event:
    """Emitted after the adapter returns successfully."""
    return Event(
        event_type="ActionExecutionCompleted",
        source="Executor",
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "duration_ms": duration_ms,
        },
    )


def create_action_execution_failed_event(
    action_id: str, action_type: str, reason: str, duration_ms: float
) -> Event:
    """Emitted after the adapter raises or a dispatch precondition fails."""
    return Event(
        event_type="ActionExecutionFailed",
        source="Executor",
        payload={
            "action_id": action_id,
            "action_type": action_type,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )


def create_adapter_resolution_failed_event(action_id: str, action_type: str) -> Event:
    """
    Emitted when no adapter is registered for the action's type.
    Distinct from UnsupportedActionType — this is a configuration error
    (adapter should exist but wasn't registered), not a protocol error.
    """
    return Event(
        event_type="AdapterResolutionFailed",
        source="Executor",
        payload={
            "action_id": action_id,
            "action_type": action_type,
        },
    )


def create_unsupported_action_type_event(action_id: str, action_type: str) -> Event:
    """
    Emitted when the ActionType is not recognised by this executor.
    This is a protocol-level error — the ActionType itself is invalid or
    not supported in this version of the runtime.
    """
    return Event(
        event_type="UnsupportedActionType",
        source="Executor",
        payload={
            "action_id": action_id,
            "action_type": action_type,
        },
    )
