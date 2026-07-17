from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.config.settings import CognitiveSettings
from cognitive_runtime.core.container import Container
from cognitive_runtime.core.pipeline import ExecutionPipeline
from cognitive_runtime.core.registry.interfaces import ServiceRegistry
from cognitive_runtime.decisions.interfaces import DecisionEngine
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import Executor
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.knowledge.interfaces import KnowledgeSystem
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.queue.interfaces import ExecutionQueue
from cognitive_runtime.rules.interfaces import RuleEngine
from cognitive_runtime.working_memory.interfaces import WorkingMemory

from .events import (
    create_runtime_started_event,
    create_runtime_stopped_event,
    create_runtime_stopping_event,
)
from .models import HealthStatus, RuntimeState


class BrainCore:
    """
    The main orchestrator of the Cognitive Runtime.
    It coordinates the initialization and shutdown of all subsystems via DI.
    """

    def __init__(self, container: Container):
        self._container = container
        self._state = RuntimeState.STOPPED
        self._services: dict[str, object] = {}
        self._settings: CognitiveSettings | None = None

    def start(self) -> None:
        """Starts the Cognitive Runtime and initializes subsystems."""
        self._state = RuntimeState.INITIALIZING
        try:
            # 1. Load config (resolved from container)
            self._settings = self._container.resolve(CognitiveSettings)

            # 2-9. Resolve subsystems
            event_bus = self._container.resolve(EventBus)
            registry = self._container.resolve(ServiceRegistry)
            memory = self._container.resolve(MemorySystem)
            knowledge = self._container.resolve(KnowledgeSystem)
            rule_engine = self._container.resolve(RuleEngine)
            goal_manager = self._container.resolve(GoalManager)
            working_memory = self._container.resolve(WorkingMemory)
            decision_engine = self._container.resolve(DecisionEngine)
            planner = self._container.resolve(Planner)

            # Keep local refs for shutdown and health
            self._services["EventBus"] = event_bus
            self._services["ServiceRegistry"] = registry
            self._services["MemorySystem"] = memory
            self._services["KnowledgeSystem"] = knowledge
            self._services["RuleEngine"] = rule_engine
            self._services["GoalManager"] = goal_manager
            self._services["WorkingMemory"] = working_memory
            self._services["DecisionEngine"] = decision_engine
            self._services["Planner"] = planner

            # 8. Register services
            registry.register(EventBus, event_bus)
            registry.register(MemorySystem, memory)
            registry.register(KnowledgeSystem, knowledge)
            registry.register(RuleEngine, rule_engine)
            registry.register(GoalManager, goal_manager)
            registry.register(WorkingMemory, working_memory)
            registry.register(DecisionEngine, decision_engine)
            registry.register(Planner, planner)

            # Resolve execution components
            executor = self._container.resolve(Executor)
            queue = self._container.resolve(ExecutionQueue)
            collector = self._container.resolve(ResultCollector)
            pipeline = self._container.resolve(ExecutionPipeline)

            self._services["Executor"] = executor
            self._services["ExecutionQueue"] = queue
            self._services["ResultCollector"] = collector
            self._services["ExecutionPipeline"] = pipeline

            registry.register(Executor, executor)
            registry.register(ExecutionQueue, queue)
            registry.register(ResultCollector, collector)
            registry.register(ExecutionPipeline, pipeline)
            
            # Start the executor (spawns threads if any, or just marks as running)
            if hasattr(executor, "start") and callable(executor.start):
                executor.start()

            # 8. Verify dependencies (implicit by resolving correctly, no deeper check defined yet)

            # 9. Publish RuntimeStarted
            event_bus.publish(create_runtime_started_event())
            self._state = RuntimeState.RUNNING

        except Exception as e:
            self._state = RuntimeState.ERROR
            raise e

    def stop(self) -> None:
        """Gracefully shuts down the Cognitive Runtime."""
        if self._state not in (RuntimeState.RUNNING, RuntimeState.INITIALIZING):
            # Already stopped or in error before full start
            pass

        self._state = RuntimeState.STOPPING

        event_bus: EventBus | None = self._services.get("EventBus")

        if event_bus:
            # 1. Flush operations (if supported by bus, none explicitly yet)

            # 2. Publish RuntimeStopping
            event_bus.publish(create_runtime_stopping_event())

        # 3. Shutdown services safely (exclude EventBus for now)
        for name, service in list(self._services.items()):
            if name == "EventBus":
                continue
            if hasattr(service, "shutdown") and callable(service.shutdown):
                try:
                    service.shutdown()
                except Exception:
                    pass

        # 4. Publish RuntimeStopped
        if event_bus:
            try:
                event_bus.publish(create_runtime_stopped_event())
            except Exception:
                pass

            # Now shutdown EventBus
            if hasattr(event_bus, "shutdown") and callable(event_bus.shutdown):
                try:
                    event_bus.shutdown()
                except Exception:
                    pass

        self._services.clear()
        self._state = RuntimeState.STOPPED

    def restart(self) -> None:
        """Restarts the Cognitive Runtime."""
        self.stop()
        self.start()

    def status(self) -> RuntimeState:
        """Returns the current state of the Runtime."""
        return self._state

    def health(self) -> HealthStatus:
        """Returns the health status of all subsystems."""
        status = HealthStatus(state=self._state, services={})

        for name, service in self._services.items():
            # In a real system, we might call service.ping() or service.health()
            # For V0.1, if it's in the dict and resolved, it's considered OK
            status.services[name] = "OK"

        return status
