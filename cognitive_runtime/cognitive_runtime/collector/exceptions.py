class CollectorError(Exception):
    """Base exception for Collector errors."""

    pass


class CollectorValidationError(CollectorError):
    """Raised when an ExecutionResult fails validation (missing required fields)."""

    pass
