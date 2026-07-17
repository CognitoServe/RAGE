from abc import ABC, abstractmethod
from collections.abc import Callable

from .models import Event

# Handlers take an event and return nothing.
EventHandler = Callable[[Event], None]


class EventBus(ABC):
    """Abstract base class defining the contract for an Event Bus."""

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publishes an event to all subscribed handlers."""
        pass

    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribes a handler to a specific event type."""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribes a handler from a specific event type."""
        pass
