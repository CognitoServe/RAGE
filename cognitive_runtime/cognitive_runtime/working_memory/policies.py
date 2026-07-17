from .interfaces import EvictionPolicy
from .models import WorkingMemoryItem


class LRUEvictionPolicy(EvictionPolicy):
    """
    Evicts the Least Recently Used (LRU) item.
    Evaluates based on the `last_accessed` timestamp.
    """

    def select_eviction(
        self, items: list[WorkingMemoryItem]
    ) -> WorkingMemoryItem | None:
        if not items:
            return None

        # Sort by last_accessed ascending (oldest first)
        # In case of tie, use inserted_at
        oldest = min(
            items,
            key=lambda item: (
                item.last_accessed.timestamp(),
                item.inserted_at.timestamp(),
            ),
        )
        return oldest
