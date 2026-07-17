"""
Action exceptions — RFC-0011

All action-specific errors inherit from ActionError, providing a single
catch-all for callers that want to handle any action-layer failure.
"""


class ActionError(Exception):
    """Base exception for all Action module errors."""


class ActionValidationError(ActionError):
    """
    Raised when an Action cannot be constructed due to invalid field values.

    This wraps underlying Pydantic validation failures so callers can catch
    a domain-specific error rather than a framework-specific one.
    """


class InvalidActionStatusTransitionError(ActionError):
    """
    Raised when an attempt is made to transition an Action to a status that
    is not reachable from its current status.

    Example: SUCCESS → RUNNING is illegal because SUCCESS is a terminal state.
    """
