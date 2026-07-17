from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """
    Common contract for all RAGE plugins.
    Plugins must be opaque, self-contained components.
    """

    @abstractmethod
    def name(self) -> str:
        """Returns the unique string identifier for this plugin."""
        pass

    @abstractmethod
    def version(self) -> str:
        """Returns the version of this plugin."""
        pass

    @abstractmethod
    def execute(self, parameters: dict[str, Any]) -> Any:
        """
        Executes the plugin logic.
        
        Args:
            parameters: A dictionary of arguments provided by the Action.
            
        Returns:
            Any serializable data that represents the result.
            
        Raises:
            Exception: Any exception raised here is caught by the Adapter
                and converted to a failed ExecutionResult.
        """
        pass


class PluginRegistryInterface(ABC):
    """
    Interface for the Plugin Registry.
    This interface is registered into the core ServiceRegistry.
    """

    @abstractmethod
    def register(self, plugin: Plugin) -> None:
        """Registers a plugin by its name."""
        pass

    @abstractmethod
    def get(self, name: str) -> Plugin:
        """Retrieves a plugin by its name."""
        pass
