from abc import ABC, abstractmethod

from .models import WorkingMemoryItem


class EvictionPolicy(ABC):
    @abstractmethod
    def select_eviction(
        self, items: list[WorkingMemoryItem]
    ) -> WorkingMemoryItem | None:
        """Returns the item to evict when capacity is reached."""
        pass


class WorkingMemory(ABC):
    @abstractmethod
    def activate(self, item: WorkingMemoryItem) -> None:
        """Adds or updates an item in working memory."""
        pass

    @abstractmethod
    def deactivate(self, item_id: str) -> None:
        """Removes an item from working memory."""
        pass

    @abstractmethod
    def contains(self, item_id: str) -> bool:
        """Checks if an item is in working memory and updates access time if it is."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Empties the working memory."""
        pass

    @abstractmethod
    def active_items(self) -> list[WorkingMemoryItem]:
        """Returns a list of all currently active items."""
        pass

    @abstractmethod
    def capacity(self) -> int:
        """Returns the current capacity limit."""
        pass

    @abstractmethod
    def set_capacity(self, limit: int) -> None:
        """Sets the capacity limit."""
        pass
