class GoalError(Exception):
    """Base exception for Goal Manager errors."""

    pass


class GoalNotFoundError(GoalError):
    """Raised when a goal is not found."""

    pass


class DuplicateGoalError(GoalError):
    """Raised when trying to create a goal with an ID that already exists."""

    pass


class InvalidStateTransitionError(GoalError):
    """Raised when a goal is updated with an invalid state transition."""

    pass
