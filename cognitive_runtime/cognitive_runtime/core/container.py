"""
Dependency Injection container for Cognitive Runtime.

This provides a lightweight, strictly-typed IoC container to wire
dependencies (services, repositories) together without global state.
"""

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Container:
    """
    A simple Dependency Injection container.
    """

    def __init__(self) -> None:
        """Initialize an empty DI container."""
        self._providers: dict[type[Any], Callable[..., Any]] = {}
        self._instances: dict[type[Any], Any] = {}

    def register(self, interface: type[T], provider: Callable[..., T]) -> None:
        """
        Register a factory function for an interface.

        Args:
            interface: The type or interface being registered.
            provider: A callable that produces an instance of the interface.
        """
        self._providers[interface] = provider

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """
        Register a singleton instance for an interface.

        Args:
            interface: The type or interface being registered.
            instance: The singleton instance.
        """
        self._instances[interface] = instance

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve an instance of the requested interface.

        Args:
            interface: The type or interface to resolve.

        Returns:
            An instance implementing the requested interface.

        Raises:
            KeyError: If the interface is not registered.
        """
        if interface in self._instances:
            return self._instances[interface]

        if interface in self._providers:
            # We don't implement automatic dependency resolution for the skeleton,
            # but in a real scenario, we'd inspect the provider's signature.
            instance = self._providers[interface]()
            return instance

        raise KeyError(f"No provider registered for {interface}")
