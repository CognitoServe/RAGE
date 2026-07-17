class DecisionError(Exception):
    """Base exception for Decision Engine errors."""

    pass


class DecisionNotFoundError(DecisionError):
    """Raised when an requested decision does not exist in history."""

    pass
