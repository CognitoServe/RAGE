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
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            # Also notify wildcard subscribers
            wildcard_handlers = list(self._handlers.get("*", []))

        for handler in handlers + wildcard_handlers:
            try:
                handler(event)
            except Exception as e:
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
