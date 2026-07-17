class PluginAdapterError(Exception):
    """Base exception for Plugin Adapter errors."""
    pass


class PluginValidationError(PluginAdapterError):
    """Raised when a plugin action fails validation."""
    pass


class PluginExecutionError(PluginAdapterError):
    """Raised when a plugin fails during execution."""
    pass


class PluginAlreadyRegisteredError(PluginAdapterError):
    """Raised when registering a plugin name that is already in use."""
    pass


class PluginNotFoundError(PluginAdapterError):
    """Raised when attempting to get a plugin that does not exist."""
    pass
