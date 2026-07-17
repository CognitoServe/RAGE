class WorkingMemoryError(Exception):
    """Base exception for Working Memory errors."""

    pass


class WorkingMemoryItemNotFoundError(WorkingMemoryError):
    """Raised when an item is not found in working memory."""

    pass
