class FilesystemAdapterError(Exception):
    """Base exception for filesystem adapter errors."""

    pass


class FilesystemValidationError(FilesystemAdapterError):
    """Raised when an action fails validation (e.g., missing target, invalid params)."""

    pass
