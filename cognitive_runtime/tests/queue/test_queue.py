"""
Tests for RFC-0012 — Execution Queue

Coverage:
  1.  Enqueue                 — basic acceptance, duplicate rejection, event
  2.  Dequeue                 — returns action, RUNNING status, None on empty
  3.  Peek                    — non-destructive, matches dequeue order
  4.  Priority ordering       — higher priority dequeues first
  5.  FIFO ordering           — equal priority preserves insertion order
  6.  Cancel (pending)        — removes from pending, event published
  7.  Cancel (running)        — removes from running, event published
  8.  Cancel (terminal)       — returns False without error
  9.  Cancel (not found)      — raises ActionNotFoundError
  10. Retry                   — failed action re-enters pending, counter incremented
  11. Retry (not found)       — raises ActionNotFoundError
  12. complete() / fail()     — executor callbacks, correct bucket placement
  13. Contains               — true/false across all buckets
  14. Size                    — reflects pending only
  15. Clear                   — empties pending, publishes event
  16. list_pending/running/completed — correct bucket snapshots
  17. Snapshot               — all bucket sizes accurate
  18. Thread safety           — concurrent producers/consumers
  19. Duplicate detection     — same action_id across buckets
  20. Event publication       — all events carry correct payloads
"""

import threading
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionStatus, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.queue.exceptions import ActionNotFoundError, DuplicateActionError
from cognitive_runtime.queue.queue import InMemoryExecutionQueue

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class CapturingEventBus(EventBus):
    """Minimal EventBus that records all published events."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)

    def subscribe(self, event_type: str, handler: Any) -> None:
        pass

    def unsubscribe(self, event_type: str, handler: Any) -> None:
        pass

    def of_type(self, event_type: str) -> list[Event]:
        with self._lock:
            return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        with self._lock:
            self.events.clear()


def make_action(
    *,
    plan_id: str = "plan-001",
    step_id: str = "step-001",
    target: str = "test://target",
    priority: int = 0,
    action_id: str | None = None,
) -> Action:
    kwargs: dict[str, Any] = dict(
        plan_id=plan_id,
        step_id=step_id,
        type=ActionType.CUSTOM,
        target=target,
        priority=priority,
    )
    if action_id is not None:
        kwargs["action_id"] = action_id
    return Action(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus() -> CapturingEventBus:
    return CapturingEventBus()


@pytest.fixture
def queue(bus: CapturingEventBus) -> InMemoryExecutionQueue:
    return InMemoryExecutionQueue(bus)


@pytest.fixture
def action() -> Action:
    return make_action(action_id="act-001")


# ---------------------------------------------------------------------------
# 1. Enqueue
# ---------------------------------------------------------------------------


class TestEnqueue:
    def test_enqueue_adds_to_pending(self, queue: InMemoryExecutionQueue, action: Action) -> None:
        queue.enqueue(action)
        assert queue.size() == 1

    def test_enqueue_transitions_action_to_queued(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        pending = queue.list_pending()
        assert len(pending) == 1
        assert pending[0].status == ActionStatus.QUEUED

    def test_enqueue_publishes_action_enqueued_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        events = bus.of_type("ActionEnqueued")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"

    def test_enqueue_duplicate_raises(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        with pytest.raises(DuplicateActionError):
            queue.enqueue(action)

    def test_enqueue_duplicate_after_dequeue_raises(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        """An action currently RUNNING (dequeued) cannot be re-enqueued."""
        queue.enqueue(action)
        queue.dequeue()
        with pytest.raises(DuplicateActionError):
            queue.enqueue(action)

    def test_enqueue_duplicate_after_complete_raises(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        """A completed action cannot be enqueued again."""
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        with pytest.raises(DuplicateActionError):
            queue.enqueue(action)

    def test_enqueue_multiple_distinct_actions(self, queue: InMemoryExecutionQueue) -> None:
        for i in range(5):
            queue.enqueue(make_action(action_id=f"act-{i}"))
        assert queue.size() == 5


# ---------------------------------------------------------------------------
# 2. Dequeue
# ---------------------------------------------------------------------------


class TestDequeue:
    def test_dequeue_empty_returns_none(self, queue: InMemoryExecutionQueue) -> None:
        assert queue.dequeue() is None

    def test_dequeue_returns_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        result = queue.dequeue()
        assert result is not None
        assert result.action_id == "act-001"

    def test_dequeue_transitions_to_running(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        result = queue.dequeue()
        assert result is not None
        assert result.status == ActionStatus.RUNNING

    def test_dequeue_removes_from_pending(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert queue.size() == 0

    def test_dequeue_moves_to_running_bucket(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert len(queue.list_running()) == 1
        assert queue.list_running()[0].action_id == "act-001"

    def test_dequeue_publishes_action_dequeued_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        events = bus.of_type("ActionDequeued")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"

    def test_dequeue_second_call_returns_none_after_single_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert queue.dequeue() is None


# ---------------------------------------------------------------------------
# 3. Peek
# ---------------------------------------------------------------------------


class TestPeek:
    def test_peek_empty_returns_none(self, queue: InMemoryExecutionQueue) -> None:
        assert queue.peek() is None

    def test_peek_returns_next_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        result = queue.peek()
        assert result is not None
        assert result.action_id == "act-001"

    def test_peek_does_not_remove_from_pending(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.peek()
        assert queue.size() == 1

    def test_peek_does_not_publish_events(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        bus.clear()
        queue.peek()
        assert len(bus.events) == 0

    def test_peek_matches_dequeue(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        peeked = queue.peek()
        dequeued = queue.dequeue()
        assert peeked is not None and dequeued is not None
        assert peeked.action_id == dequeued.action_id


# ---------------------------------------------------------------------------
# 4. Priority ordering
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_higher_priority_dequeues_first(self, queue: InMemoryExecutionQueue) -> None:
        low = make_action(action_id="low", priority=1)
        high = make_action(action_id="high", priority=10)
        # Enqueue low first, then high
        queue.enqueue(low)
        queue.enqueue(high)
        first = queue.dequeue()
        assert first is not None
        assert first.action_id == "high"

    def test_priority_ordering_with_three_levels(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        queue.enqueue(make_action(action_id="p0", priority=0))
        queue.enqueue(make_action(action_id="p5", priority=5))
        queue.enqueue(make_action(action_id="p3", priority=3))
        order = []
        while queue.size():
            result = queue.dequeue()
            if result:
                order.append(result.action_id)
                queue.complete(result.action_id)
        assert order == ["p5", "p3", "p0"]

    def test_negative_priority_dequeues_last(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        queue.enqueue(make_action(action_id="neg", priority=-5))
        queue.enqueue(make_action(action_id="zero", priority=0))
        first = queue.dequeue()
        assert first is not None
        assert first.action_id == "zero"


# ---------------------------------------------------------------------------
# 5. FIFO ordering within equal priority
# ---------------------------------------------------------------------------


class TestFIFOOrdering:
    def test_fifo_within_equal_priority(self, queue: InMemoryExecutionQueue) -> None:
        ids = [f"act-{i}" for i in range(5)]
        for aid in ids:
            queue.enqueue(make_action(action_id=aid, priority=0))
        dequeued = []
        while queue.size():
            result = queue.dequeue()
            if result:
                dequeued.append(result.action_id)
                queue.complete(result.action_id)
        assert dequeued == ids

    def test_fifo_preserved_after_higher_priority_drains(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        """Low-priority FIFO ordering is preserved while high-priority drains."""
        queue.enqueue(make_action(action_id="lo-1", priority=0))
        queue.enqueue(make_action(action_id="lo-2", priority=0))
        queue.enqueue(make_action(action_id="hi-1", priority=10))

        # hi-1 comes first
        first = queue.dequeue()
        assert first is not None and first.action_id == "hi-1"
        queue.complete(first.action_id)

        # then lo-1 before lo-2
        second = queue.dequeue()
        third = queue.dequeue()
        assert second is not None and second.action_id == "lo-1"
        assert third is not None and third.action_id == "lo-2"


# ---------------------------------------------------------------------------
# 6 & 7. Cancel
# ---------------------------------------------------------------------------


class TestCancel:
    def test_cancel_pending_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        result = queue.cancel(action.action_id)
        assert result is True
        assert queue.size() == 0

    def test_cancel_pending_publishes_cancelled_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.cancel(action.action_id)
        events = bus.of_type("ActionCancelled")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"

    def test_cancel_running_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        result = queue.cancel(action.action_id)
        assert result is True
        assert len(queue.list_running()) == 0

    def test_cancel_running_publishes_cancelled_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.cancel(action.action_id)
        events = bus.of_type("ActionCancelled")
        assert any(e.payload["action_id"] == "act-001" for e in events)

    def test_cancel_terminal_action_returns_false(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        result = queue.cancel(action.action_id)
        assert result is False

    def test_cancel_unknown_action_raises(self, queue: InMemoryExecutionQueue) -> None:
        with pytest.raises(ActionNotFoundError):
            queue.cancel("ghost-id")

    def test_cancelled_action_cannot_be_dequeued(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.cancel(action.action_id)
        assert queue.dequeue() is None

    def test_contains_returns_true_for_cancelled_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.cancel(action.action_id)
        assert queue.contains(action.action_id)


# ---------------------------------------------------------------------------
# 10 & 11. Retry
# ---------------------------------------------------------------------------


class TestRetry:
    def _make_failed_action(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "simulated failure")

    def test_retry_moves_to_pending(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        self._make_failed_action(queue, action)
        queue.retry(action.action_id)
        assert queue.size() == 1

    def test_retry_increments_attempt_counter(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        self._make_failed_action(queue, action)
        queue.retry(action.action_id)
        pending = queue.list_pending()
        assert pending[0].metadata.get("retry_attempt") == 1

    def test_retry_twice_increments_counter_correctly(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        self._make_failed_action(queue, action)
        queue.retry(action.action_id)
        # Run it again and fail again
        queue.dequeue()
        queue.fail(action.action_id, "second failure")
        queue.retry(action.action_id)
        pending = queue.list_pending()
        assert pending[0].metadata.get("retry_attempt") == 2

    def test_retry_publishes_retried_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        self._make_failed_action(queue, action)
        queue.retry(action.action_id)
        events = bus.of_type("ActionRetried")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"
        assert events[0].payload["attempt"] == 1

    def test_retry_not_found_raises(self, queue: InMemoryExecutionQueue) -> None:
        with pytest.raises(ActionNotFoundError):
            queue.retry("ghost-id")

    def test_retry_pending_action_raises(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        with pytest.raises(ActionNotFoundError):
            queue.retry(action.action_id)

    def test_retried_action_obeys_priority_ordering(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        high = make_action(action_id="hi", priority=10)
        queue.enqueue(action)  # priority 0
        queue.dequeue()
        queue.fail(action.action_id, "err")
        queue.retry(action.action_id)  # back in pending at priority 0

        queue.enqueue(high)  # priority 10

        first = queue.dequeue()
        assert first is not None and first.action_id == "hi"


# ---------------------------------------------------------------------------
# 12. complete() / fail()
# ---------------------------------------------------------------------------


class TestExecutorCallbacks:
    def test_complete_moves_to_completed_bucket(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        assert len(queue.list_completed()) == 1
        assert queue.list_completed()[0].status == ActionStatus.SUCCESS

    def test_complete_publishes_action_completed_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        events = bus.of_type("ActionCompleted")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"

    def test_complete_unknown_raises(self, queue: InMemoryExecutionQueue) -> None:
        with pytest.raises(ActionNotFoundError):
            queue.complete("ghost-id")

    def test_fail_moves_to_failed_bucket(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "disk error")
        snap = queue.snapshot()
        assert snap.failed_count == 1

    def test_fail_publishes_action_failed_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "network timeout")
        events = bus.of_type("ActionFailed")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"
        assert events[0].payload["reason"] == "network timeout"

    def test_fail_unknown_raises(self, queue: InMemoryExecutionQueue) -> None:
        with pytest.raises(ActionNotFoundError):
            queue.fail("ghost-id", "reason")

    def test_failed_action_status_is_failed(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "err")
        snap = queue.snapshot()
        assert snap.failed_count == 1
        assert snap.running_count == 0


# ---------------------------------------------------------------------------
# 13. Contains
# ---------------------------------------------------------------------------


class TestContains:
    def test_contains_pending(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        assert queue.contains(action.action_id)

    def test_contains_running(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert queue.contains(action.action_id)

    def test_contains_completed(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        assert queue.contains(action.action_id)

    def test_contains_failed(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "err")
        assert queue.contains(action.action_id)

    def test_not_contains_unknown(self, queue: InMemoryExecutionQueue) -> None:
        assert not queue.contains("ghost-id")


# ---------------------------------------------------------------------------
# 14. Size
# ---------------------------------------------------------------------------


class TestSize:
    def test_size_zero_initially(self, queue: InMemoryExecutionQueue) -> None:
        assert queue.size() == 0

    def test_size_increments_on_enqueue(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        for i in range(3):
            queue.enqueue(make_action(action_id=f"a{i}"))
        assert queue.size() == 3

    def test_size_decrements_on_dequeue(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert queue.size() == 0

    def test_size_does_not_count_running(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        assert queue.size() == 0

    def test_size_does_not_count_completed(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        assert queue.size() == 0


# ---------------------------------------------------------------------------
# 15. Clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_empties_pending(self, queue: InMemoryExecutionQueue) -> None:
        for i in range(4):
            queue.enqueue(make_action(action_id=f"a{i}"))
        queue.clear()
        assert queue.size() == 0

    def test_clear_publishes_queue_cleared_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        for i in range(3):
            queue.enqueue(make_action(action_id=f"a{i}"))
        bus.clear()
        queue.clear()
        events = bus.of_type("ActionQueueCleared")
        assert len(events) == 1
        assert events[0].payload["cleared_count"] == 3

    def test_clear_does_not_publish_event_when_empty(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        queue.clear()
        assert len(bus.of_type("ActionQueueCleared")) == 0

    def test_clear_does_not_affect_running(
        self, queue: InMemoryExecutionQueue, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        extra = make_action(action_id="extra")
        queue.enqueue(extra)
        queue.clear()
        assert len(queue.list_running()) == 1

    def test_cleared_actions_go_to_cancelled_bucket(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        for i in range(3):
            queue.enqueue(make_action(action_id=f"a{i}"))
        queue.clear()
        snap = queue.snapshot()
        assert snap.cancelled_count == 3


# ---------------------------------------------------------------------------
# 16. List methods
# ---------------------------------------------------------------------------


class TestListMethods:
    def test_list_pending_in_scheduling_order(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        queue.enqueue(make_action(action_id="lo", priority=0))
        queue.enqueue(make_action(action_id="hi", priority=5))
        pending = queue.list_pending()
        assert [a.action_id for a in pending] == ["hi", "lo"]

    def test_list_running_empty_initially(self, queue: InMemoryExecutionQueue) -> None:
        assert queue.list_running() == []

    def test_list_completed_accumulates(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        for i in range(3):
            a = make_action(action_id=f"a{i}")
            queue.enqueue(a)
            queue.dequeue()
            queue.complete(a.action_id)
        assert len(queue.list_completed()) == 3


# ---------------------------------------------------------------------------
# 17. Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_snapshot_all_zeros_initially(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        snap = queue.snapshot()
        assert snap.pending_count == 0
        assert snap.running_count == 0
        assert snap.completed_count == 0
        assert snap.failed_count == 0
        assert snap.cancelled_count == 0

    def test_snapshot_reflects_all_buckets(
        self, queue: InMemoryExecutionQueue
    ) -> None:
        # 1 completed — enqueue, dequeue, and complete in isolation
        a_done = make_action(action_id="d1")
        queue.enqueue(a_done)
        queue.dequeue()
        queue.complete(a_done.action_id)

        # 1 failed — enqueue, dequeue, and fail in isolation
        a_fail = make_action(action_id="f1")
        queue.enqueue(a_fail)
        queue.dequeue()
        queue.fail(a_fail.action_id, "err")

        # 1 running — dequeued but not resolved
        a_run = make_action(action_id="r1")
        queue.enqueue(a_run)
        queue.dequeue()

        # 1 pending — left in queue
        queue.enqueue(make_action(action_id="p1"))

        snap = queue.snapshot()
        assert snap.pending_count == 1
        assert snap.running_count == 1
        assert snap.completed_count == 1
        assert snap.failed_count == 1
        assert snap.cancelled_count == 0
        assert snap.total_processed == 2

    def test_snapshot_is_frozen(self, queue: InMemoryExecutionQueue) -> None:
        from pydantic import ValidationError

        snap = queue.snapshot()
        with pytest.raises((ValidationError, TypeError)):
            snap.pending_count = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 18. Thread Safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_enqueue_dequeue(self, queue: InMemoryExecutionQueue) -> None:
        """
        20 producer threads each enqueue one action.
        20 consumer threads each attempt one dequeue.
        No races or corrupted state after all threads finish.
        """
        n = 20
        actions = [make_action(action_id=f"t-{i}") for i in range(n)]
        errors: list[Exception] = []

        def producer(a: Action) -> None:
            try:
                queue.enqueue(a)
            except Exception as e:
                errors.append(e)

        def consumer() -> None:
            try:
                result = queue.dequeue()
                if result:
                    queue.complete(result.action_id)
            except Exception as e:
                errors.append(e)

        producers = [threading.Thread(target=producer, args=(a,)) for a in actions]
        consumers = [threading.Thread(target=consumer) for _ in range(n)]

        all_threads = producers + consumers
        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        snap = queue.snapshot()
        # Every action is accounted for somewhere
        total = (
            snap.pending_count
            + snap.running_count
            + snap.completed_count
            + snap.failed_count
            + snap.cancelled_count
        )
        assert total == n

    def test_concurrent_cancel(self, queue: InMemoryExecutionQueue) -> None:
        """Concurrent cancel attempts on the same action_id are safe."""
        action = make_action(action_id="shared")
        queue.enqueue(action)

        results: list[bool | Exception] = []
        lock = threading.Lock()

        def try_cancel() -> None:
            try:
                r = queue.cancel("shared")
                with lock:
                    results.append(r)
            except ActionNotFoundError:
                with lock:
                    results.append(False)
            except Exception as e:
                with lock:
                    results.append(e)

        threads = [threading.Thread(target=try_cancel) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        exceptions = [r for r in results if isinstance(r, Exception)]
        assert not exceptions, f"Unexpected exceptions: {exceptions}"
        # Exactly one cancel should succeed (True), rest should return False
        assert results.count(True) == 1

    def test_concurrent_enqueue_unique_ids(self, queue: InMemoryExecutionQueue) -> None:
        """Each thread enqueues a unique action — all should succeed without corruption."""
        n = 50
        errors: list[Exception] = []

        def enqueue_unique(i: int) -> None:
            try:
                queue.enqueue(make_action(action_id=f"unique-{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=enqueue_unique, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert queue.size() == n


# ---------------------------------------------------------------------------
# 20. Event publication integrity
# ---------------------------------------------------------------------------


class TestEventPublicationIntegrity:
    def test_enqueue_event_carries_priority_and_sequence(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        a = make_action(action_id="evt-001", priority=7)
        queue.enqueue(a)
        e = bus.of_type("ActionEnqueued")[0]
        assert e.payload["priority"] == 7
        assert "sequence" in e.payload

    def test_dequeue_event_carries_priority(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        e = bus.of_type("ActionDequeued")[0]
        assert e.payload["action_id"] == "act-001"
        assert "priority" in e.payload

    def test_retried_event_carries_attempt(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        queue.enqueue(action)
        queue.dequeue()
        queue.fail(action.action_id, "err")
        queue.retry(action.action_id)
        e = bus.of_type("ActionRetried")[0]
        assert e.payload["attempt"] == 1

    def test_cleared_event_carries_count(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        for i in range(4):
            queue.enqueue(make_action(action_id=f"ce-{i}"))
        bus.clear()
        queue.clear()
        e = bus.of_type("ActionQueueCleared")[0]
        assert e.payload["cleared_count"] == 4

    def test_all_events_are_frozen(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus, action: Action
    ) -> None:
        from pydantic import ValidationError

        queue.enqueue(action)
        queue.dequeue()
        queue.complete(action.action_id)
        for event in bus.events:
            with pytest.raises((ValidationError, TypeError)):
                event.event_type = "hacked"  # type: ignore[misc]
