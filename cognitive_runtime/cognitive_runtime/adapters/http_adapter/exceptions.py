class HttpAdapterError(Exception):
    """Base exception for HTTP adapter errors."""
    pass

class HttpValidationError(HttpAdapterError):
    """Raised when an HTTP action fails validation (e.g., missing URL, bad scheme)."""
    pass
