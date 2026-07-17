"""
Actions Module — RFC-0011

The Action Model is the universal executable instruction used by RAGE.
It is a pure data container — it never executes, never reasons, never learns.

Public API
----------
Action            — The core immutable action descriptor.
ActionType        — Enum of all supported action categories.
ActionStatus      — Enum of all possible lifecycle states.
ActionResultReference — A pointer to where a result is stored.
"""

from .events import (
    create_action_cancelled_event,
    create_action_completed_event,
    create_action_created_event,
    create_action_failed_event,
    create_action_queued_event,
    create_action_started_event,
)
from .exceptions import ActionValidationError, InvalidActionStatusTransitionError
from .models import Action, ActionResultReference, ActionStatus, ActionType

__all__ = [
    # Core models
    "Action",
    "ActionType",
    "ActionStatus",
    "ActionResultReference",
    # Exceptions
    "ActionValidationError",
    "InvalidActionStatusTransitionError",
    # Event factories
    "create_action_created_event",
    "create_action_queued_event",
    "create_action_started_event",
    "create_action_completed_event",
    "create_action_failed_event",
    "create_action_cancelled_event",
]
