class ServiceRegistryError(Exception):
    """Base exception for all Service Registry errors."""

    pass


class ServiceAlreadyRegisteredError(ServiceRegistryError):
    """Raised when an implementation is already registered for a given interface."""

    pass


class ServiceNotFoundError(ServiceRegistryError):
    """Raised when a requested service interface is not found in the registry."""

    pass
