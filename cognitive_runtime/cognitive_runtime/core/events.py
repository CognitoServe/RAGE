from cognitive_runtime.events.models import Event


def create_runtime_started_event(source: str = "BrainCore") -> Event:
    return Event(event_type="RuntimeStarted", source=source)


def create_runtime_stopping_event(source: str = "BrainCore") -> Event:
    return Event(event_type="RuntimeStopping", source=source)


def create_runtime_stopped_event(source: str = "BrainCore") -> Event:
    return Event(event_type="RuntimeStopped", source=source)
