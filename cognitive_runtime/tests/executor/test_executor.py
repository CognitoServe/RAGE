"""
Tests for RFC-0013 — Executor

Coverage:
  1.  Lifecycle                — start / stop / is_running / idempotency
  2.  Happy path               — submit → execute_next → SUCCESS
  3.  execute() directly       — dispatch a RUNNING action, get result
  4.  Missing adapter          — AdapterNotFoundError, AdapterResolutionFailed event
  5.  Invalid action state     — non-RUNNING action raises InvalidActionStateError
  6.  Already terminal         — CANCELLED/SUCCESS/FAILED rejects dispatch
  7.  Duplicate execution      — same action_id concurrent → DuplicateExecutionError
  8.  Cancellation             — submit → cancel → execute_next returns None
  9.  Queue interaction        — queue.complete() on success; queue.fail() on failure
  10. Statistics               — counters accumulate correctly
  11. Event publication        — all 7 events with correct payloads
  12. Adapter failure          — adapter raises → failure result, queue.fail() called
  13. execute_next before start — raises ExecutorNotRunningError
  14. Thread safety            — concurrent submits + sequential execute_next
  15. Architecture constraint  — no planner/goals/memory/knowledge imports
"""

import threading
import time
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionStatus, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.executor.exceptions import (
    DuplicateExecutionError,
    ExecutorNotRunningError,
    InvalidActionStateError,
)
from cognitive_runtime.executor.executor import DefaultExecutor
from cognitive_runtime.executor.interfaces import ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult
from cognitive_runtime.queue.queue import InMemoryExecutionQueue

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class CapturingEventBus(EventBus):
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


class SuccessAdapter(ActionAdapter):
    """Adapter that always returns a successful result."""

    def __init__(self, output: dict[str, Any] | None = None, delay: float = 0.0) -> None:
        self._output = output or {"status": "ok"}
        self._delay = delay

    def execute(self, action: Action) -> ExecutionResult:
        if self._delay:
            time.sleep(self._delay)
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.type,
            success=True,
            output=self._output,
            duration_ms=self._delay * 1000,
        )

    def supports(self, action_type: ActionType) -> bool:
        return True


class FailingAdapter(ActionAdapter):
    """Adapter that always raises an exception."""

    def __init__(self, error_message: str = "adapter failure") -> None:
        self._error = error_message

    def execute(self, action: Action) -> ExecutionResult:
        raise RuntimeError(self._error)

    def supports(self, action_type: ActionType) -> bool:
        return True


class ReturnsFailureAdapter(ActionAdapter):
    """Adapter that returns a failure result without raising."""

    def execute(self, action: Action) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.type,
            success=False,
            error="explicit failure from adapter",
        )

    def supports(self, action_type: ActionType) -> bool:
        return True


def make_action(
    *,
    action_id: str = "act-001",
    action_type: ActionType = ActionType.CUSTOM,
    priority: int = 0,
    status: ActionStatus = ActionStatus.PENDING,
) -> Action:
    kwargs: dict[str, Any] = dict(
        action_id=action_id,
        plan_id="plan-001",
        step_id="step-001",
        type=action_type,
        target="test://target",
        priority=priority,
    )
    if status != ActionStatus.PENDING:
        kwargs["status"] = status
    return Action(**kwargs)


def make_running_action(**kwargs: Any) -> Action:
    """Shortcut for a RUNNING action (for direct execute() calls)."""
    return make_action(status=ActionStatus.RUNNING, **kwargs)


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
def executor(
    queue: InMemoryExecutionQueue, bus: CapturingEventBus
) -> DefaultExecutor:
    ex = DefaultExecutor(queue=queue, event_bus=bus)
    ex.register_adapter(ActionType.CUSTOM, SuccessAdapter())
    return ex


@pytest.fixture
def started_executor(executor: DefaultExecutor) -> DefaultExecutor:
    executor.start()
    return executor


# ---------------------------------------------------------------------------
# 1. Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_not_running_initially(self, executor: DefaultExecutor) -> None:
        assert not executor.is_running()

    def test_start_sets_running(self, executor: DefaultExecutor) -> None:
        executor.start()
        assert executor.is_running()

    def test_stop_clears_running(self, executor: DefaultExecutor) -> None:
        executor.start()
        executor.stop()
        assert not executor.is_running()

    def test_start_is_idempotent(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        executor.start()
        # Only one ExecutorStarted event
        assert len(bus.of_type("ExecutorStarted")) == 1

    def test_stop_is_idempotent(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        executor.stop()
        executor.stop()
        assert len(bus.of_type("ExecutorStopped")) == 1

    def test_start_publishes_executor_started_event(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        assert len(bus.of_type("ExecutorStarted")) == 1

    def test_stop_publishes_executor_stopped_event(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        executor.stop()
        assert len(bus.of_type("ExecutorStopped")) == 1

    def test_restart_after_stop(self, executor: DefaultExecutor) -> None:
        executor.start()
        executor.stop()
        executor.start()
        assert executor.is_running()


# ---------------------------------------------------------------------------
# 2. Happy path — submit → execute_next → SUCCESS
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_submit_then_execute_next_succeeds(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        action = make_action()
        started_executor.submit(action)
        result = started_executor.execute_next()
        assert result is not None
        assert result.success is True
        assert result.action_id == "act-001"

    def test_result_has_correct_action_type(
        self, started_executor: DefaultExecutor
    ) -> None:
        started_executor.submit(make_action(action_type=ActionType.CUSTOM))
        result = started_executor.execute_next()
        assert result is not None
        assert result.action_type == ActionType.CUSTOM

    def test_result_has_no_error_on_success(
        self, started_executor: DefaultExecutor
    ) -> None:
        started_executor.submit(make_action())
        result = started_executor.execute_next()
        assert result is not None
        assert result.error is None

    def test_queue_complete_called_on_success(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        started_executor.submit(make_action())
        started_executor.execute_next()
        snap = queue.snapshot()
        assert snap.completed_count == 1
        assert snap.running_count == 0

    def test_execute_next_returns_none_on_empty_queue(
        self, started_executor: DefaultExecutor
    ) -> None:
        assert started_executor.execute_next() is None

    def test_output_from_adapter_is_passed_through(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, SuccessAdapter(output={"key": "value"}))
        executor.start()
        executor.submit(make_action())
        result = executor.execute_next()
        assert result is not None
        assert result.output == {"key": "value"}


# ---------------------------------------------------------------------------
# 3. execute() directly
# ---------------------------------------------------------------------------


class TestDirectExecute:
    def test_execute_running_action_directly(
        self, started_executor: DefaultExecutor
    ) -> None:
        action = make_running_action()
        result = started_executor.execute(action)
        assert result.success is True
        assert result.action_id == "act-001"

    def test_execute_does_not_touch_queue(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        action = make_running_action()
        started_executor.execute(action)
        snap = queue.snapshot()
        # Nothing was enqueued or dequeued
        assert snap.pending_count == 0
        assert snap.completed_count == 0

    def test_execute_returns_duration_ms(
        self, started_executor: DefaultExecutor
    ) -> None:
        action = make_running_action()
        result = started_executor.execute(action)
        assert result.duration_ms >= 0.0


# ---------------------------------------------------------------------------
# 4. Missing adapter
# ---------------------------------------------------------------------------


class TestMissingAdapter:
    def test_execute_without_adapter_returns_failure(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.start()
        # No adapter registered
        result = executor.execute(make_running_action(action_type=ActionType.HTTP_GET))
        assert result.success is False
        assert result.error is not None

    def test_missing_adapter_publishes_resolution_failed_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.start()
        executor.execute(make_running_action(action_type=ActionType.HTTP_GET))
        events = bus.of_type("AdapterResolutionFailed")
        assert len(events) == 1
        assert events[0].payload["action_type"] == ActionType.HTTP_GET

    def test_missing_adapter_increments_failure_count(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.start()
        executor.execute(make_running_action(action_type=ActionType.HTTP_GET))
        assert executor.stats().failure_count == 1


# ---------------------------------------------------------------------------
# 5 & 6. Invalid / terminal action states
# ---------------------------------------------------------------------------


class TestInvalidActionState:
    def test_pending_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.PENDING))

    def test_queued_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.QUEUED))

    def test_success_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.SUCCESS))

    def test_failed_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.FAILED))

    def test_cancelled_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.CANCELLED))

    def test_timeout_action_raises(self, started_executor: DefaultExecutor) -> None:
        with pytest.raises(InvalidActionStateError):
            started_executor.execute(make_action(status=ActionStatus.TIMEOUT))


# ---------------------------------------------------------------------------
# 7. Duplicate execution guard
# ---------------------------------------------------------------------------


class TestDuplicateExecution:
    def test_duplicate_action_id_raises(
        self, started_executor: DefaultExecutor
    ) -> None:
        """
        Simulate concurrent dispatch of the same action_id by injecting the
        id into _executing before the second call. The executor uses the set
        as the guard.
        """
        action = make_running_action()

        # Manually pre-populate the executing set to simulate a concurrent dispatch
        with started_executor._lock:
            started_executor._executing.add(action.action_id)

        with pytest.raises(DuplicateExecutionError):
            started_executor.execute(action)

        # Cleanup
        with started_executor._lock:
            started_executor._executing.discard(action.action_id)

    def test_slot_released_after_successful_dispatch(
        self, started_executor: DefaultExecutor
    ) -> None:
        action = make_running_action(action_id="release-test")
        started_executor.execute(action)
        with started_executor._lock:
            assert "release-test" not in started_executor._executing

    def test_slot_released_after_failed_dispatch(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter())
        executor.start()
        action = make_running_action(action_id="fail-release-test")
        executor.execute(action)
        with executor._lock:
            assert "fail-release-test" not in executor._executing


# ---------------------------------------------------------------------------
# 8. Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    def test_cancel_pending_prevents_execution(
        self, started_executor: DefaultExecutor
    ) -> None:
        action = make_action()
        started_executor.submit(action)
        started_executor.cancel(action.action_id)
        result = started_executor.execute_next()
        assert result is None

    def test_cancel_delegates_to_queue(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        action = make_action()
        started_executor.submit(action)
        started_executor.cancel(action.action_id)
        snap = queue.snapshot()
        assert snap.cancelled_count == 1


# ---------------------------------------------------------------------------
# 9. Queue interaction (complete / fail callbacks)
# ---------------------------------------------------------------------------


class TestQueueInteraction:
    def test_execute_next_calls_queue_complete_on_success(
        self,
        started_executor: DefaultExecutor,
        queue: InMemoryExecutionQueue,
    ) -> None:
        started_executor.submit(make_action())
        started_executor.execute_next()
        assert queue.snapshot().completed_count == 1

    def test_execute_next_calls_queue_fail_on_adapter_raise(
        self,
        queue: InMemoryExecutionQueue,
        bus: CapturingEventBus,
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter())
        executor.start()
        executor.submit(make_action())
        executor.execute_next()
        assert queue.snapshot().failed_count == 1

    def test_execute_next_calls_queue_fail_on_returned_failure(
        self,
        queue: InMemoryExecutionQueue,
        bus: CapturingEventBus,
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, ReturnsFailureAdapter())
        executor.start()
        executor.submit(make_action())
        executor.execute_next()
        assert queue.snapshot().failed_count == 1


# ---------------------------------------------------------------------------
# 10. Statistics
# ---------------------------------------------------------------------------


class TestStatistics:
    def test_stats_initial_state(self, executor: DefaultExecutor) -> None:
        s = executor.stats()
        assert s.is_running is False
        assert s.total_executed == 0
        assert s.success_count == 0
        assert s.failure_count == 0
        assert s.current_action_id is None
        assert s.last_error is None

    def test_stats_reflect_running_state(
        self, started_executor: DefaultExecutor
    ) -> None:
        assert started_executor.stats().is_running is True

    def test_total_executed_increments(
        self, started_executor: DefaultExecutor
    ) -> None:
        for i in range(3):
            started_executor.submit(make_action(action_id=f"a{i}"))
            started_executor.execute_next()
        assert started_executor.stats().total_executed == 3

    def test_success_count_increments(
        self, started_executor: DefaultExecutor
    ) -> None:
        started_executor.submit(make_action())
        started_executor.execute_next()
        assert started_executor.stats().success_count == 1

    def test_failure_count_increments(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter())
        executor.start()
        executor.submit(make_action())
        executor.execute_next()
        assert executor.stats().failure_count == 1

    def test_last_error_set_on_failure(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter("disk full"))
        executor.start()
        executor.submit(make_action())
        executor.execute_next()
        assert executor.stats().last_error is not None
        assert "disk full" in executor.stats().last_error

    def test_last_error_cleared_implicitly_by_success(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        """last_error is overwritten on failure, not cleared on success — verify it persists."""
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter("err"))
        executor.start()
        executor.submit(make_action(action_id="fail"))
        executor.execute_next()
        assert executor.stats().last_error is not None

        # Now swap adapter and run a success
        executor.register_adapter(ActionType.CUSTOM, SuccessAdapter())
        executor.submit(make_action(action_id="ok"))
        executor.execute_next()
        # last_error still holds the last failure (success doesn't wipe it)
        assert executor.stats().last_error is not None

    def test_average_execution_time_computed(
        self, started_executor: DefaultExecutor
    ) -> None:
        started_executor.submit(make_action())
        started_executor.execute_next()
        s = started_executor.stats()
        assert s.average_execution_time_ms >= 0.0

    def test_stats_is_frozen(self, started_executor: DefaultExecutor) -> None:
        from pydantic import ValidationError

        s = started_executor.stats()
        with pytest.raises((ValidationError, TypeError)):
            s.total_executed = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 11. Event publication
# ---------------------------------------------------------------------------


class TestEventPublication:
    def test_executor_started_event(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        assert len(bus.of_type("ExecutorStarted")) == 1

    def test_executor_stopped_event(
        self, executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        executor.start()
        executor.stop()
        assert len(bus.of_type("ExecutorStopped")) == 1

    def test_action_execution_started_event(
        self, started_executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        started_executor.execute(make_running_action())
        events = bus.of_type("ActionExecutionStarted")
        assert len(events) == 1
        assert events[0].payload["action_id"] == "act-001"
        assert events[0].payload["action_type"] == ActionType.CUSTOM

    def test_action_execution_completed_event(
        self, started_executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        started_executor.execute(make_running_action())
        events = bus.of_type("ActionExecutionCompleted")
        assert len(events) == 1
        assert "duration_ms" in events[0].payload

    def test_action_execution_failed_event_on_adapter_raise(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter("boom"))
        executor.start()
        executor.execute(make_running_action())
        events = bus.of_type("ActionExecutionFailed")
        assert len(events) == 1
        assert "boom" in events[0].payload["reason"]

    def test_adapter_resolution_failed_event(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.start()
        executor.execute(make_running_action(action_type=ActionType.HTTP_POST))
        assert len(bus.of_type("AdapterResolutionFailed")) == 1

    def test_all_events_are_frozen(
        self, started_executor: DefaultExecutor, bus: CapturingEventBus
    ) -> None:
        from pydantic import ValidationError

        started_executor.execute(make_running_action())
        for event in bus.events:
            with pytest.raises((ValidationError, TypeError)):
                event.source = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 12. Adapter failure handling
# ---------------------------------------------------------------------------


class TestAdapterFailureHandling:
    def test_adapter_raise_produces_failure_result(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter("boom"))
        executor.start()
        result = executor.execute(make_running_action())
        assert result.success is False
        assert result.error is not None
        assert "boom" in result.error

    def test_adapter_raise_does_not_propagate(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        """execute() must never raise an exception from adapter internals."""
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, FailingAdapter())
        executor.start()
        # Should not raise
        result = executor.execute(make_running_action())
        assert result is not None

    def test_returned_failure_result_respected(
        self, queue: InMemoryExecutionQueue, bus: CapturingEventBus
    ) -> None:
        executor = DefaultExecutor(queue=queue, event_bus=bus)
        executor.register_adapter(ActionType.CUSTOM, ReturnsFailureAdapter())
        executor.start()
        result = executor.execute(make_running_action())
        assert result.success is False


# ---------------------------------------------------------------------------
# 13. execute_next before start
# ---------------------------------------------------------------------------


class TestExecutorNotRunning:
    def test_execute_next_before_start_raises(
        self, executor: DefaultExecutor
    ) -> None:
        with pytest.raises(ExecutorNotRunningError):
            executor.execute_next()

    def test_execute_before_start_raises(
        self, executor: DefaultExecutor
    ) -> None:
        with pytest.raises(ExecutorNotRunningError):
            executor.execute(make_running_action())

    def test_execute_after_stop_raises(self, executor: DefaultExecutor) -> None:
        executor.start()
        executor.stop()
        with pytest.raises(ExecutorNotRunningError):
            executor.execute(make_running_action())


# ---------------------------------------------------------------------------
# 14. Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_submits_all_enqueue(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        n = 30
        errors: list[Exception] = []

        def submit(i: int) -> None:
            try:
                started_executor.submit(make_action(action_id=f"t-{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert queue.size() == n

    def test_sequential_execute_next_processes_all(
        self, started_executor: DefaultExecutor, queue: InMemoryExecutionQueue
    ) -> None:
        n = 10
        for i in range(n):
            started_executor.submit(make_action(action_id=f"seq-{i}"))
        results = []
        while True:
            r = started_executor.execute_next()
            if r is None:
                break
            results.append(r)
        assert len(results) == n
        assert all(r.success for r in results)

    def test_register_adapter_thread_safe(
        self, executor: DefaultExecutor
    ) -> None:
        """Concurrent adapter registration must not corrupt the registry."""
        errors: list[Exception] = []

        def register(i: int) -> None:
            try:
                executor.register_adapter(ActionType.CUSTOM, SuccessAdapter())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ---------------------------------------------------------------------------
# 15. Architecture constraint
# ---------------------------------------------------------------------------


class TestArchitectureConstraints:
    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.executor.executor as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.planner" not in source
        assert "import planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.executor.executor as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.goals" not in source

    def test_no_memory_imports(self) -> None:
        import inspect

        import cognitive_runtime.executor.executor as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.memory" not in source
        assert "from cognitive_runtime.working_memory" not in source

    def test_no_knowledge_imports(self) -> None:
        import inspect

        import cognitive_runtime.executor.executor as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.knowledge" not in source

    def test_no_os_module_import(self) -> None:
        import inspect

        import cognitive_runtime.executor.executor as mod
        source = inspect.getsource(mod)
        assert "import os" not in source
        assert "import subprocess" not in source
        assert "import pathlib" not in source
