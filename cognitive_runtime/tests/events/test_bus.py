from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event


def test_event_immutability():
    """Test that the Event model is immutable."""
    event = Event(event_type="TestEvent", source="test", payload={"key": "value"})

    with pytest.raises(ValidationError):
        event.event_type = "NewType"

    with pytest.raises(ValidationError):
        event.payload["new_key"] = (
            "new_value"  # This raises because dict mutating is not caught
            # by pydantic frozen on top level, but reassigning payload is.
        )
        event.payload = {}


def test_event_creation_defaults():
    """Test that Event model generates correct defaults."""
    event = Event(event_type="TestEvent", source="test")
    assert event.event_id is not None
    assert isinstance(event.timestamp, datetime)
    assert event.timestamp.tzinfo == UTC
    assert event.correlation_id is None
    assert event.payload == {}
    assert event.metadata == {}


def test_subscribe_publish():
    """Test subscribing to and publishing an event."""
    bus = SynchronousEventBus()
    received_events: list[Event] = []

    def handler(_event: Event) -> None:
        received_events.append(_event)

    bus.subscribe("TestEvent", handler)

    test_event = Event(event_type="TestEvent", source="test")
    bus.publish(test_event)

    assert len(received_events) == 1
    assert received_events[0] == test_event


def test_unsubscribe():
    """Test unsubscribing a handler."""
    bus = SynchronousEventBus()
    received_events: list[Event] = []

    def handler(_event: Event) -> None:
        received_events.append(_event)

    bus.subscribe("TestEvent", handler)
    bus.unsubscribe("TestEvent", handler)

    test_event = Event(event_type="TestEvent", source="test")
    bus.publish(test_event)

    assert len(received_events) == 0


def test_multiple_subscribers():
    """Test multiple subscribers receive the same event in order."""
    bus = SynchronousEventBus()
    received_order: list[str] = []

    def handler1(_event: Event) -> None:
        received_order.append("handler1")

    def handler2(_event: Event) -> None:
        received_order.append("handler2")

    bus.subscribe("TestEvent", handler1)
    bus.subscribe("TestEvent", handler2)

    test_event = Event(event_type="TestEvent", source="test")
    bus.publish(test_event)

    assert received_order == ["handler1", "handler2"]


def test_publish_zero_subscribers():
    """Test publishing with no subscribers doesn't fail."""
    bus = SynchronousEventBus()
    test_event = Event(event_type="TestEvent", source="test")
    # Should not raise any exception
    bus.publish(test_event)


def test_invalid_handler():
    """Test subscribing a non-callable raises TypeError."""
    bus = SynchronousEventBus()
    with pytest.raises(TypeError):
        bus.subscribe("TestEvent", "not_a_callable")  # type: ignore


def test_failing_handler():
    """Test that a failing handler does not stop other handlers."""
    bus = SynchronousEventBus()
    received_events = []

    def handler_fail(_event: Event) -> None:
        raise ValueError("I failed")

    def handler_success(_event: Event) -> None:
        received_events.append(_event)

    bus.subscribe("TestEvent", handler_fail)
    bus.subscribe("TestEvent", handler_success)

    test_event = Event(event_type="TestEvent", source="test")
    bus.publish(test_event)

    assert len(received_events) == 1
    assert received_events[0] == test_event


def test_unsubscribe_nonexistent_handler():
    """Test unsubscribing a handler that wasn't subscribed doesn't fail."""
    bus = SynchronousEventBus()

    def handler(_event: Event) -> None:
        pass

    # Should not raise ValueError
    bus.unsubscribe("TestEvent", handler)


def test_thread_safety_publish():
    """Test that handlers are isolated from subscriptions during publish."""
    bus = SynchronousEventBus()
    events = []

    def malicious_handler(_event: Event) -> None:
        # Tries to subscribe another handler during execution
        bus.subscribe("TestEvent", lambda _e: events.append("late"))
        events.append("malicious")

    bus.subscribe("TestEvent", malicious_handler)
    test_event = Event(event_type="TestEvent", source="test")

    # Should execute without Deadlock
    # The late handler won't be called for *this* event because the list was copied
    bus.publish(test_event)
    assert events == ["malicious"]

    # Second publish should hit both
    bus.publish(test_event)
    assert events == ["malicious", "malicious", "late"]


def test_failing_handler_logs_traceback():
    from unittest.mock import patch

    def handler_fail(_event: Event) -> None:
        raise ValueError("I failed")

    bus = SynchronousEventBus()
    bus.subscribe("TestEvent", handler_fail)

    with patch("cognitive_runtime.events.bus.logger.error") as mock_log:
        bus.publish(Event(event_type="TestEvent", source="test"))
        mock_log.assert_called_once()
        assert mock_log.call_args[1].get("exc_info") is True
