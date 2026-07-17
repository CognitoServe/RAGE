"""
Queue exceptions — RFC-0012

All queue-specific errors inherit from QueueError, giving callers a single
catch point for any scheduling-layer failure.
"""


class QueueError(Exception):
    """Base exception for all Execution Queue errors."""


class QueueFullError(QueueError):
    """
    Raised when the queue has reached its capacity limit.

    Reserved for future use when a max_size constraint is enforced.
    """


class ActionNotFoundError(QueueError):
    """
    Raised when cancel() or retry() is called with an action_id that is not
    present in any bucket (pending, running, or failed).
    """


class DuplicateActionError(QueueError):
    """
    Raised when enqueue() receives an action whose action_id is already tracked
    by the queue in any bucket (pending, running, completed, failed, cancelled).
    """
