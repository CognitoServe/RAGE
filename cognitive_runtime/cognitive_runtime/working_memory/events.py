from cognitive_runtime.events.models import Event


def create_wm_activated_event(item_id: str, source: str = "WorkingMemory") -> Event:
    return Event(
        event_type="WorkingMemoryActivated", payload={"item_id": item_id}, source=source
    )


def create_wm_deactivated_event(item_id: str, source: str = "WorkingMemory") -> Event:
    return Event(
        event_type="WorkingMemoryDeactivated",
        payload={"item_id": item_id},
        source=source,
    )


def create_wm_evicted_event(item_id: str, source: str = "WorkingMemory") -> Event:
    return Event(
        event_type="WorkingMemoryEvicted", payload={"item_id": item_id}, source=source
    )


def create_wm_cleared_event(source: str = "WorkingMemory") -> Event:
    return Event(event_type="WorkingMemoryCleared", payload={}, source=source)
