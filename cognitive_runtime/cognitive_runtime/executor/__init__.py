"""
Executor Module — RFC-0013

The orchestration bridge between the Execution Queue and Action Adapters.

Public API
----------
Executor            — Abstract interface.
DefaultExecutor     — Concrete V1 implementation.
ActionAdapter       — Abstract adapter interface.
ExecutionResult     — Immutable dispatch outcome record.
ExecutorStats       — Immutable observability snapshot.
"""

from .events import (
    create_action_execution_completed_event,
    create_action_execution_failed_event,
    create_action_execution_started_event,
    create_adapter_resolution_failed_event,
    create_executor_started_event,
    create_executor_stopped_event,
    create_unsupported_action_type_event,
)
from .exceptions import (
    AdapterNotFoundError,
    DuplicateExecutionError,
    ExecutorError,
    ExecutorNotRunningError,
    InvalidActionStateError,
)
from .executor import DefaultExecutor
from .interfaces import ActionAdapter, Executor
from .models import ExecutionResult, ExecutorStats

__all__ = [
    # Interfaces
    "Executor",
    "ActionAdapter",
    # Implementation
    "DefaultExecutor",
    # Models
    "ExecutionResult",
    "ExecutorStats",
    # Exceptions
    "ExecutorError",
    "ExecutorNotRunningError",
    "AdapterNotFoundError",
    "InvalidActionStateError",
    "DuplicateExecutionError",
    # Event factories
    "create_executor_started_event",
    "create_executor_stopped_event",
    "create_action_execution_started_event",
    "create_action_execution_completed_event",
    "create_action_execution_failed_event",
    "create_adapter_resolution_failed_event",
    "create_unsupported_action_type_event",
]
