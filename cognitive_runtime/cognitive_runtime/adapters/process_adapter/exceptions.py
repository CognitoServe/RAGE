class ProcessAdapterError(Exception):
    """Base exception for Process Adapter errors."""
    pass


class ProcessValidationError(ProcessAdapterError):
    """Raised when a process action fails validation."""
    pass
