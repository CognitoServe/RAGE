from abc import ABC, abstractmethod

from .models import Experience, ExperienceStatus, SearchQuery


class MemoryRepository(ABC):
    """Abstract interface for Memory storage operations."""

    @abstractmethod
    def save(self, experience: Experience) -> None:
        pass

    @abstractmethod
    def get(self, memory_id: str) -> Experience:
        pass

    @abstractmethod
    def search(self, query: SearchQuery) -> list[Experience]:
        pass

    @abstractmethod
    def update_status(self, memory_id: str, status: ExperienceStatus) -> None:
        pass


class MemorySystem(ABC):
    """Abstract interface for the Memory cognitive subsystem."""

    @abstractmethod
    def remember(self, experience: Experience) -> None:
        pass

    @abstractmethod
    def recall(self, memory_id: str) -> Experience:
        pass

    @abstractmethod
    def search(self, query: SearchQuery) -> list[Experience]:
        pass

    @abstractmethod
    def archive(self, memory_id: str) -> None:
        pass
