import os
import sys
import threading
from typing import Any

import pytest

from cognitive_runtime.actions.models import ActionType
from cognitive_runtime.adapters.plugin_adapter.interfaces import (
    Plugin,
    PluginRegistryInterface,
)
from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.core.container import Container
from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.core.pipeline import ExecutionPipeline
from cognitive_runtime.decisions.interfaces import DecisionEngine
from cognitive_runtime.decisions.models import Decision
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.goals.models import Goal
from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.planner.models import Step, StepStatus


class DummyPlugin(Plugin):
    def name(self) -> str:
        return "IntegrationPlugin"

    def version(self) -> str:
        return "1.0.0"

    def execute(self, parameters: dict[str, Any]) -> Any:
        return {"result": parameters.get("value", 0) * 10}


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        self._lock = threading.Lock()
        
        # Subscribe to all events by intercepting publish
        self._original_publish = bus.publish
        bus.publish = self._intercept_publish

    def _intercept_publish(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)
        self._original_publish(event)

    def get_events(self) -> list[Event]:
        with self._lock:
            return list(self.events)


@pytest.fixture
def runtime_env() -> dict[str, Any]:
    # Startup the runtime
    brain = startup()
    container: Container = brain._container
    
    # Resolve essential components
    event_bus = container.resolve(EventBus)
    goal_manager = container.resolve(GoalManager)
    planner = container.resolve(Planner)
    pipeline = container.resolve(ExecutionPipeline)
    decision_engine = container.resolve(DecisionEngine)
    
    # Mock decision engine to always return a dummy decision
    decision_engine.decide = lambda ctx: Decision(
        decision_id="d-1",
        context_items=[],
        matched_rules=[],
        candidate_actions=[],
        selected_action=None,
        explanation="Test mock",
    )
    
    # Register Dummy Plugin
    from cognitive_runtime.core.registry.interfaces import ServiceRegistry
    registry = container.resolve(ServiceRegistry)
    plugin_registry = registry.get(PluginRegistryInterface)
    plugin_registry.register(DummyPlugin())

    # Attach Event Collector
    event_collector = EventCollector(event_bus)
    
    yield {
        "brain": brain,
        "container": container,
        "goal_manager": goal_manager,
        "planner": planner,
        "pipeline": pipeline,
        "event_collector": event_collector,
    }
    
    shutdown(brain)


def test_scenario_1_file_write(runtime_env: dict[str, Any], tmp_path: Any) -> None:
    # Goal: Write a file
    goal_manager: GoalManager = runtime_env["goal_manager"]
    planner: Planner = runtime_env["planner"]
    pipeline: ExecutionPipeline = runtime_env["pipeline"]
    events: EventCollector = runtime_env["event_collector"]

    target_file = str(tmp_path / "test_file.txt")
    
    # 1. Create Goal
    goal = Goal(
        goal_id="g-1",
        title="Write File",
        description="Write a test file",
    )
    goal_manager.create(goal)
    
    # 2. Override planner strategy to return our specific step
    planner._strategy.generate_steps = lambda _g_id, _ctx: [
        Step(
            step_id="step-1",
            order=1,
            description="Write a test file",
            action_type=ActionType.FILE_WRITE,
            target=target_file,
            parameters={"content": "Hello Pipeline"},
            status=StepStatus.PENDING,
        )
    ]

    # 3. Tick pipeline to enqueue the step
    pipeline.tick()
    
    # 4. Tick pipeline to execute the enqueued action
    pipeline.tick()
    
    # 5. Verify outcome
    assert os.path.exists(target_file)
    with open(target_file) as f:
        assert f.read() == "Hello Pipeline"
        
    # Check events
    event_types = [e.event_type for e in events.get_events()]
    assert "ResultCollected" in event_types


def test_scenario_2_http_get(runtime_env: dict[str, Any]) -> None:
    # Goal: HTTP GET
    goal_manager: GoalManager = runtime_env["goal_manager"]
    planner: Planner = runtime_env["planner"]
    pipeline: ExecutionPipeline = runtime_env["pipeline"]

    goal = Goal(
        goal_id="g-2",
        title="Fetch example",
        description="Fetch example.com",
    )
    goal_manager.create(goal)
    planner._strategy.generate_steps = lambda _g_id, _ctx: [
        Step(
            step_id="step-2",
            order=1,
            description="Fetch example.com",
            action_type=ActionType.HTTP_GET,
            target="http://example.com",
            parameters={},
            status=StepStatus.PENDING,
        )
    ]
    
    pipeline.tick() # Creates plan and enqueues
    pipeline.tick() # execute
    
    # Check events
    collector = runtime_env["container"].resolve(ResultCollector)
    latest_obs = collector.latest()
    assert latest_obs is not None
    assert latest_obs.success is True

def test_scenario_3_plugin_execution(runtime_env: dict[str, Any]) -> None:
    # Goal: Execute Plugin
    goal_manager: GoalManager = runtime_env["goal_manager"]
    planner: Planner = runtime_env["planner"]
    pipeline: ExecutionPipeline = runtime_env["pipeline"]

    goal = Goal(
        goal_id="g-3",
        title="Run Plugin",
        description="Run IntegrationPlugin",
    )
    goal_manager.create(goal)
    planner._strategy.generate_steps = lambda _g_id, _ctx: [
        Step(
            step_id="step-3",
            order=1,
            description="Run Plugin",
            action_type=ActionType.PLUGIN_CALL,
            target="IntegrationPlugin",
            parameters={"value": 4},
            status=StepStatus.PENDING,
        )
    ]
    
    pipeline.tick() # Creates plan and enqueues
    pipeline.tick() # execute
    
    # Verify result collected contains the correct output
    collector = runtime_env["container"].resolve(ResultCollector)
    latest_obs = collector.latest()
    assert latest_obs is not None
    assert latest_obs.success is True
    assert latest_obs.result_summary == {"result": 40}


def test_scenario_4_process_launch(runtime_env: dict[str, Any]) -> None:
    # Goal: Launch Process
    goal_manager: GoalManager = runtime_env["goal_manager"]
    planner: Planner = runtime_env["planner"]
    pipeline: ExecutionPipeline = runtime_env["pipeline"]

    goal = Goal(
        goal_id="g-4",
        title="Run Process",
        description="Run python version",
    )
    goal_manager.create(goal)
    planner._strategy.generate_steps = lambda _g_id, _ctx: [
        Step(
            step_id="step-4",
            order=1,
            description="Run process",
            action_type=ActionType.PROCESS_START,
            target=sys.executable,
            parameters={"args": ["--version"]},
            status=StepStatus.PENDING,
        )
    ]
    
    pipeline.tick() # Creates plan and enqueues
    pipeline.tick() # execute
    
    # Verify result collected
    collector = runtime_env["container"].resolve(ResultCollector)
    latest_obs = collector.latest()
    assert latest_obs is not None
    assert latest_obs.success is True
    # The output from python --version usually goes to stdout
    assert "Python" in latest_obs.result_summary["stdout"]
