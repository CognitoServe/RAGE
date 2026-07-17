from abc import ABC, abstractmethod
from typing import Any, TypeVar

T = TypeVar("T")


class ServiceRegistry(ABC):
    """Abstract interface defining the Service Registry."""

    @abstractmethod
    def register(self, interface_type: type[T], implementation: T) -> None:
        """Register a singleton implementation for a specific interface."""
        pass

    @abstractmethod
    def unregister(self, interface_type: type[T]) -> None:
        """Unregister the implementation for a specific interface."""
        pass

    @abstractmethod
    def get(self, interface_type: type[T]) -> T:
        """Retrieve the implementation for a specific interface."""
        pass

    @abstractmethod
    def contains(self, interface_type: type[T]) -> bool:
        """Check if an implementation is registered for a specific interface."""
        pass

    @abstractmethod
    def list_services(self) -> list[type[Any]]:
        """List all registered service interfaces."""
        pass
