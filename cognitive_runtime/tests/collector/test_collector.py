import threading
from typing import Any

import pytest

from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.collector.exceptions import CollectorValidationError
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.executor.models import ExecutionResult
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.memory.models import Experience, SearchQuery
from cognitive_runtime.working_memory.interfaces import WorkingMemory
from cognitive_runtime.working_memory.models import WorkingMemoryItem


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


class MockWorkingMemory(WorkingMemory):
    def __init__(self) -> None:
        self.items: dict[str, WorkingMemoryItem] = {}

    def activate(self, item: WorkingMemoryItem) -> None:
        self.items[item.item_id] = item

    def deactivate(self, item_id: str) -> None:
        self.items.pop(item_id, None)

    def contains(self, item_id: str) -> bool:
        return item_id in self.items

    def clear(self) -> None:
        self.items.clear()

    def active_items(self) -> list[WorkingMemoryItem]:
        return list(self.items.values())

    def capacity(self) -> int:
        return 100

    def set_capacity(self, limit: int) -> None:
        pass


class MockMemorySystem(MemorySystem):
    def __init__(self) -> None:
        self.experiences: list[Experience] = []

    def remember(self, experience: Experience) -> None:
        self.experiences.append(experience)

    def recall(self, memory_id: str) -> Experience:
        for exp in self.experiences:
            if exp.memory_id == memory_id:
                return exp
        raise KeyError()

    def search(self, _query: SearchQuery) -> list[Experience]:
        return []

    def archive(self, memory_id: str) -> None:
        pass


@pytest.fixture
def bus() -> MockEventBus:
    return MockEventBus()


@pytest.fixture
def wm() -> MockWorkingMemory:
    return MockWorkingMemory()


@pytest.fixture
def ltm() -> MockMemorySystem:
    return MockMemorySystem()


@pytest.fixture
def collector(
    bus: MockEventBus, wm: MockWorkingMemory, ltm: MockMemorySystem
) -> ResultCollector:
    return ResultCollector(bus, wm, ltm)


def make_result(
    success: bool,
    action_id: str = "act-1",
    plan_id: str | None = "plan-1",
    correlation_id: str | None = "corr-1",
) -> ExecutionResult:
    return ExecutionResult(
        action_id=action_id,
        action_type="FILE_READ",
        success=success,
        output={"data": "hello"} if success else None,
        error=None if success else "failed",
        duration_ms=100.0,
        metadata={"plan_id": plan_id, "correlation_id": correlation_id}
        if plan_id or correlation_id
        else {},
    )


class TestCollector:
    def test_collect_success(
        self,
        collector: ResultCollector,
        wm: MockWorkingMemory,
        ltm: MockMemorySystem,
        bus: MockEventBus,
    ) -> None:
        res = make_result(True)
        collector.collect(res)

        obs = collector.latest()
        assert obs is not None
        assert obs.action_id == "act-1"
        assert obs.success is True
        assert obs.result_summary == {"data": "hello"}

        # Verify WM integration
        assert len(wm.items) == 1
        assert list(wm.items.values())[0].item_id == obs.observation_id

        # Verify LTM integration
        assert len(ltm.experiences) == 1
        assert ltm.experiences[0].memory_id == obs.observation_id
        assert ltm.experiences[0].payload["action_id"] == "act-1"

        # Verify Events
        event_types = {e.event_type for e in bus.events}
        assert "ResultCollected" in event_types
        assert "ObservationCreated" in event_types
        assert "ExecutionRecorded" in event_types
        assert "StatisticsUpdated" in event_types

    def test_collect_failure(self, collector: ResultCollector) -> None:
        res = make_result(False)
        collector.collect(res)

        obs = collector.latest()
        assert obs is not None
        assert obs.success is False
        assert obs.result_summary == "failed"

    def test_validation(self, collector: ResultCollector) -> None:
        res = ExecutionResult(
            action_id="",  # Empty, should fail
            action_type="FILE_READ",
            success=True,
        )
        with pytest.raises(CollectorValidationError):
            collector.collect(res)

    def test_history_and_clear(self, collector: ResultCollector) -> None:
        collector.collect(make_result(True, action_id="1"))
        collector.collect(make_result(False, action_id="2"))

        assert len(collector.history()) == 2

        collector.clear()
        assert len(collector.history()) == 0
        assert collector.statistics().total_executions == 0

    def test_find(self, collector: ResultCollector) -> None:
        collector.collect(
            make_result(True, action_id="A", plan_id="P1", correlation_id="C1")
        )
        collector.collect(
            make_result(False, action_id="B", plan_id="P1", correlation_id="C2")
        )
        collector.collect(
            make_result(True, action_id="C", plan_id="P2", correlation_id="C2")
        )

        assert len(collector.find(action_id="A")) == 1
        assert len(collector.find(plan_id="P1")) == 2
        assert len(collector.find(correlation_id="C2")) == 2
        assert len(collector.find(action_id="Z")) == 0

    def test_statistics(self, collector: ResultCollector) -> None:
        assert collector.statistics().total_executions == 0

        collector.collect(make_result(True, action_id="1"))
        stats = collector.statistics()
        assert stats.total_executions == 1
        assert stats.successful_executions == 1
        assert stats.success_rate == 1.0
        assert stats.failure_rate == 0.0

        collector.collect(make_result(False, action_id="2"))
        stats = collector.statistics()
        assert stats.total_executions == 2
        assert stats.successful_executions == 1
        assert stats.failed_executions == 1
        assert stats.success_rate == 0.5
        assert stats.failure_rate == 0.5
        assert stats.average_duration_ms == 100.0

    def test_thread_safety(self, collector: ResultCollector) -> None:
        def worker() -> None:
            for i in range(100):
                collector.collect(make_result(True, action_id=str(i)))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert collector.statistics().total_executions == 500
        assert len(collector.history()) == 500


class TestArchitectureConstraints:
    def test_no_filesystem_imports(self) -> None:
        import inspect

        import cognitive_runtime.collector.collector as mod

        source = inspect.getsource(mod)
        assert "adapters.filesystem" not in source

    def test_no_http_imports(self) -> None:
        import inspect

        import cognitive_runtime.collector.collector as mod

        source = inspect.getsource(mod)
        assert "adapters.http" not in source

    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.collector.collector as mod

        source = inspect.getsource(mod)
        assert "planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.collector.collector as mod

        source = inspect.getsource(mod)
        assert "goals" not in source
