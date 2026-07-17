from abc import ABC, abstractmethod

from .models import Goal


class GoalManager(ABC):
    """
    Abstract interface for the Goal Manager subsystem.
    Manages the lifecycle and state of goals.
    """

    @abstractmethod
    def create(self, goal: Goal) -> None:
        """Registers a new goal."""
        pass

    @abstractmethod
    def update(self, goal: Goal) -> None:
        """Updates an existing goal's state/properties."""
        pass

    @abstractmethod
    def complete(self, goal_id: str) -> None:
        """Marks a goal as COMPLETED."""
        pass

    @abstractmethod
    def cancel(self, goal_id: str) -> None:
        """Marks a goal as CANCELLED."""
        pass

    @abstractmethod
    def list(self) -> list[Goal]:
        """Returns all currently tracked active goals."""
        pass

    @abstractmethod
    def highest_priority(self) -> Goal | None:
        """Returns the active goal with the highest priority score."""
        pass
