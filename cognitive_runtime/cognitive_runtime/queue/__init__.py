"""
Execution Queue Module — RFC-0012

The scheduling layer between the Planner and a future Executor.

The queue receives Actions, orders them deterministically by priority and
insertion order, and exposes them one at a time. It tracks all lifecycle
state (pending, running, completed, failed, cancelled) and publishes
events at every transition.

Public API
----------
ExecutionQueue          — Abstract interface.
InMemoryExecutionQueue  — Concrete V1 implementation.
QueueSnapshot           — Read-only observability model.
"""

from .events import (
    create_action_dequeued_event,
    create_action_enqueued_event,
    create_action_retried_event,
    create_queue_cleared_event,
)
from .exceptions import (
    ActionNotFoundError,
    DuplicateActionError,
    QueueError,
    QueueFullError,
)
from .interfaces import ExecutionQueue
from .models import QueueSnapshot
from .queue import InMemoryExecutionQueue

__all__ = [
    # Interface
    "ExecutionQueue",
    # Implementation
    "InMemoryExecutionQueue",
    # Models
    "QueueSnapshot",
    # Exceptions
    "QueueError",
    "QueueFullError",
    "ActionNotFoundError",
    "DuplicateActionError",
    # Event factories
    "create_action_enqueued_event",
    "create_action_dequeued_event",
    "create_action_retried_event",
    "create_queue_cleared_event",
]
