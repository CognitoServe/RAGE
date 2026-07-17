import sys
import threading
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.adapters.process_adapter.adapter import ProcessAdapter
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event


class MockEventBus(EventBus):
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


@pytest.fixture
def bus() -> MockEventBus:
    return MockEventBus()


@pytest.fixture
def adapter(bus: MockEventBus) -> ProcessAdapter:
    return ProcessAdapter(bus)


def make_action(type_: ActionType, target: str, **params: Any) -> Action:
    return Action(
        plan_id="plan-1",
        step_id="step-1",
        type=type_,
        target=target,
        parameters=params,
    )


class TestProcessAdapter:
    def test_supports(self, adapter: ProcessAdapter) -> None:
        assert adapter.supports(ActionType.PROCESS_START) is True
        assert adapter.supports(ActionType.PROCESS_STOP) is True
        assert adapter.supports(ActionType.FILE_READ) is False

    def test_validation_missing_target(self, adapter: ProcessAdapter) -> None:
        action = make_action(ActionType.PROCESS_START, "")
        res = adapter.execute(action)
        assert res.success is False
        assert "Target is required" in res.error

    def test_validation_invalid_args(self, adapter: ProcessAdapter) -> None:
        action = make_action(ActionType.PROCESS_START, "python", args="not_a_list")
        res = adapter.execute(action)
        assert res.success is False
        assert "list of strings" in res.error

    def test_validation_invalid_timeout(self, adapter: ProcessAdapter) -> None:
        action = make_action(ActionType.PROCESS_START, "python", timeout="30s")
        res = adapter.execute(action)
        assert res.success is False
        assert "must be a number" in res.error

    def test_start_success(self, adapter: ProcessAdapter, bus: MockEventBus) -> None:
        # Run a simple python print command
        action = make_action(
            ActionType.PROCESS_START,
            sys.executable,
            args=["-c", "print('hello world')"],
        )
        res = adapter.execute(action)
        
        assert res.success is True
        assert res.error is None
        assert res.output is not None
        assert res.output["exit_code"] == 0
        assert "hello world" in res.output["stdout"]
        
        # Verify events
        event_types = {e.event_type for e in bus.events}
        assert "ProcessStarted" in event_types
        assert "ProcessCompleted" in event_types
        assert "ProcessFailed" not in event_types

    def test_start_failure(self, adapter: ProcessAdapter) -> None:
        # Run a python command that raises an error
        action = make_action(
            ActionType.PROCESS_START,
            sys.executable,
            args=["-c", "import sys; sys.exit(1)"],
        )
        res = adapter.execute(action)
        
        assert res.success is False
        assert res.output is not None
        assert res.output["exit_code"] == 1

    def test_start_not_found(self, adapter: ProcessAdapter) -> None:
        action = make_action(ActionType.PROCESS_START, "does_not_exist_at_all_123")
        res = adapter.execute(action)
        
        assert res.success is False
        assert "Executable not found" in res.error

    def test_start_timeout(self, adapter: ProcessAdapter) -> None:
        action = make_action(
            ActionType.PROCESS_START,
            sys.executable,
            args=["-c", "import time; time.sleep(5)"],
            timeout=0.1
        )
        res = adapter.execute(action)
        
        assert res.success is False
        assert "timed out after 0.1 seconds" in res.error

    def test_stop_invalid_pid(self, adapter: ProcessAdapter) -> None:
        action = make_action(ActionType.PROCESS_STOP, "not_a_pid")
        res = adapter.execute(action)
        
        assert res.success is False
        assert "valid integer PID" in res.error

    def test_stop_not_found(self, adapter: ProcessAdapter) -> None:
        # Assuming pid 999999 is not running
        action = make_action(ActionType.PROCESS_STOP, "999999")
        res = adapter.execute(action)
        
        assert res.success is False
        assert res.output is not None
        assert res.output["exit_code"] == 1
        assert "not found" in res.error or "Failed to stop process" in res.error

    def test_security_no_shell(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "shell=True" not in source


class TestArchitectureConstraints:
    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "goals" not in source

    def test_no_memory_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "memory" not in source

    def test_no_filesystem_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "filesystem" not in source

    def test_no_http_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.process_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "adapters.http" not in source
