"""
Executor exceptions — RFC-0013

All executor-specific errors inherit from ExecutorError, giving callers a
single catch point for any orchestration-layer failure.
"""


class ExecutorError(Exception):
    """Base exception for all Executor module errors."""


class ExecutorNotRunningError(ExecutorError):
    """
    Raised when execute() or execute_next() is called on an Executor that has
    not been started via start(), or has already been stopped.
    """


class AdapterNotFoundError(ExecutorError):
    """
    Raised when the executor cannot resolve an ActionAdapter for the given
    ActionType. No adapter has been registered for that type.
    """


class InvalidActionStateError(ExecutorError):
    """
    Raised when an Action is presented to execute() in an invalid state.

    The Executor only accepts Actions that are RUNNING. Actions in PENDING,
    QUEUED, or any terminal state (SUCCESS, FAILED, CANCELLED, TIMEOUT)
    are rejected.
    """


class DuplicateExecutionError(ExecutorError):
    """
    Raised when execute() is called for an action_id that is already being
    dispatched by this executor instance.

    This guards against concurrent double-dispatch of the same action.
    """
