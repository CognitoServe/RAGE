class PlannerError(Exception):
    """Base class for all planner exceptions."""

    pass


class PlanNotFoundError(PlannerError):
    """Raised when a plan cannot be found."""

    pass


class InvalidPlanStateError(PlannerError):
    """Raised when an operation is performed on a plan in an invalid state."""

    pass
