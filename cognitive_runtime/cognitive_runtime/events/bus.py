import contextlib
import threading

import structlog

from .interfaces import EventBus, EventHandler
from .models import Event

logger = structlog.get_logger(__name__)


class SynchronousEventBus(EventBus):
    """
    A strictly synchronous implementation of the EventBus.
    Uses a threading lock to ensure safe modifications to subscriptions.
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        """Publishes an event synchronously to all registered handlers."""
        # We copy the handlers list inside the lock to avoid deadlocks
        # or issues if a handler subscribes/unsubscribes during execution.
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # We log the error but don't stop other handlers from running.
                # Core infrastructure must be resilient.
                logger.error(
                    "event_handler_failed",
                    event_id=event.event_id,
                    event_type=event.event_type,
                    handler=str(handler),
                    error=str(e),
                    exc_info=True,
                )

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if not callable(handler):
            raise TypeError("Handler must be callable")

        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            if event_type in self._handlers:
                with contextlib.suppress(ValueError):
                    self._handlers[event_type].remove(handler)
