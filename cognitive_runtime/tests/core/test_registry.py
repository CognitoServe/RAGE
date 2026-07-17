import contextlib
import threading

import pytest

from cognitive_runtime.core.registry.exceptions import (
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
)
from cognitive_runtime.core.registry.registry import SynchronousServiceRegistry
from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event


# Dummy interfaces for testing
class DummyInterface:
    def do_something(self):
        pass


class DummyImplementation(DummyInterface):
    def do_something(self):
        return "done"


class AnotherInterface:
    pass


@pytest.fixture
def event_bus():
    return SynchronousEventBus()


@pytest.fixture
def registry(event_bus):
    return SynchronousServiceRegistry(event_bus=event_bus)


def test_successful_registration_and_retrieval(registry, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("ServiceRegistered", lambda e: published_events.append(e))

    impl = DummyImplementation()
    registry.register(DummyInterface, impl)

    assert registry.contains(DummyInterface) is True
    assert registry.get(DummyInterface) is impl
    assert DummyInterface in registry.list_services()

    assert len(published_events) == 1
    assert published_events[0].payload["interface"] == "DummyInterface"
    assert published_events[0].payload["implementation"] == "DummyImplementation"


def test_duplicate_registration(registry):
    impl1 = DummyImplementation()
    impl2 = DummyImplementation()

    registry.register(DummyInterface, impl1)

    with pytest.raises(ServiceAlreadyRegisteredError):
        registry.register(DummyInterface, impl2)


def test_unknown_service_retrieval(registry):
    with pytest.raises(ServiceNotFoundError):
        registry.get(DummyInterface)

    assert registry.contains(DummyInterface) is False


def test_unregister(registry, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("ServiceUnregistered", lambda e: published_events.append(e))

    impl = DummyImplementation()
    registry.register(DummyInterface, impl)
    registry.unregister(DummyInterface)

    assert registry.contains(DummyInterface) is False
    with pytest.raises(ServiceNotFoundError):
        registry.get(DummyInterface)

    assert len(published_events) == 1
    assert published_events[0].payload["interface"] == "DummyInterface"

    # Unregistering non-existent should fail gracefully
    registry.unregister(AnotherInterface)
    assert len(published_events) == 1  # Event not published if it didn't exist


def test_concurrent_registration_and_lookup(registry):
    # Testing thread safety
    def register_worker():
        impl = DummyImplementation()
        with contextlib.suppress(ServiceAlreadyRegisteredError):
            registry.register(DummyInterface, impl)

    def read_worker():
        with contextlib.suppress(ServiceNotFoundError):
            registry.get(DummyInterface)

    threads = []
    for _ in range(10):
        threads.append(threading.Thread(target=register_worker))
        threads.append(threading.Thread(target=read_worker))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert registry.contains(DummyInterface) is True
    # Verify no multiple registrations corrupted state
    assert len(registry.list_services()) == 1


def test_type_validation(registry):
    with pytest.raises(TypeError):
        # type: ignore
        registry.register("not_a_type", DummyImplementation())
