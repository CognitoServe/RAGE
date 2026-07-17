import threading

from .exceptions import (
    PluginAlreadyRegisteredError,
    PluginNotFoundError,
)
from .interfaces import Plugin, PluginRegistryInterface


class DefaultPluginRegistry(PluginRegistryInterface):
    """
    Thread-safe registry for plugins.
    Allows mapping a string plugin name to the actual Plugin instance.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._lock = threading.Lock()

    def register(self, plugin: Plugin) -> None:
        name = plugin.name()
        with self._lock:
            if name in self._plugins:
                raise PluginAlreadyRegisteredError(
                    f"Plugin '{name}' is already registered."
                )
            self._plugins[name] = plugin

    def get(self, name: str) -> Plugin:
        with self._lock:
            if name not in self._plugins:
                raise PluginNotFoundError(f"Plugin '{name}' not found.")
            return self._plugins[name]
