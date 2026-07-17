from cognitive_runtime.events.models import Event


def create_service_registered_event(
    interface_name: str, implementation_name: str, source: str
) -> Event:
    return Event(
        event_type="ServiceRegistered",
        source=source,
        payload={"interface": interface_name, "implementation": implementation_name},
    )


def create_service_unregistered_event(interface_name: str, source: str) -> Event:
    return Event(
        event_type="ServiceUnregistered",
        source=source,
        payload={"interface": interface_name},
    )
