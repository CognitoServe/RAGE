import threading
from typing import Any, TypeVar

from cognitive_runtime.events.interfaces import EventBus

from .events import create_service_registered_event, create_service_unregistered_event
from .exceptions import ServiceAlreadyRegisteredError, ServiceNotFoundError
from .interfaces import ServiceRegistry

T = TypeVar("T")


class SynchronousServiceRegistry(ServiceRegistry):
    def __init__(self, event_bus: EventBus):
        self._services: dict[type[Any], Any] = {}
        self._lock = threading.Lock()
        self._event_bus = event_bus
        self._source_name = "ServiceRegistry"

    def register(self, interface_type: type[T], implementation: T) -> None:
        if not isinstance(interface_type, type):
            raise TypeError("interface_type must be a type/class.")

        with self._lock:
            if interface_type in self._services:
                raise ServiceAlreadyRegisteredError(
                    f"A service is already registered for interface "
                    f"{interface_type.__name__}"
                )
            self._services[interface_type] = implementation

        event = create_service_registered_event(
            interface_name=interface_type.__name__,
            implementation_name=implementation.__class__.__name__,
            source=self._source_name,
        )
        self._event_bus.publish(event)

    def unregister(self, interface_type: type[T]) -> None:
        with self._lock:
            # The RFC states: "Unregistering a non-existent service
            # must fail gracefully"
            if interface_type in self._services:
                del self._services[interface_type]
            else:
                return

        event = create_service_unregistered_event(
            interface_name=interface_type.__name__, source=self._source_name
        )
        self._event_bus.publish(event)

    def get(self, interface_type: type[T]) -> T:
        with self._lock:
            if interface_type not in self._services:
                raise ServiceNotFoundError(
                    f"No service registered for interface {interface_type.__name__}"
                )
            return self._services[interface_type]

    def contains(self, interface_type: type[T]) -> bool:
        with self._lock:
            return interface_type in self._services

    def list_services(self) -> list[type[Any]]:
        with self._lock:
            return list(self._services.keys())
