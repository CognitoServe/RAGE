"""
Lifecycle management for Cognitive Runtime.

This module handles the startup and shutdown sequences, ensuring
that all subsystems (logging, storage, events) are properly initialized
and gracefully terminated.
"""

from cognitive_runtime.actions.models import ActionType
from cognitive_runtime.adapters.filesystem.adapter import FilesystemAdapter
from cognitive_runtime.adapters.http_adapter.adapter import HttpAdapter
from cognitive_runtime.adapters.plugin_adapter.adapter import PluginAdapter
from cognitive_runtime.adapters.plugin_adapter.interfaces import PluginRegistryInterface
from cognitive_runtime.adapters.plugin_adapter.registry import DefaultPluginRegistry
from cognitive_runtime.adapters.process_adapter.adapter import ProcessAdapter
from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.config.settings import CognitiveSettings, load_settings
from cognitive_runtime.core.brain import BrainCore
from cognitive_runtime.core.container import Container
from cognitive_runtime.core.pipeline import ExecutionPipeline
from cognitive_runtime.core.registry.interfaces import ServiceRegistry
from cognitive_runtime.core.registry.registry import SynchronousServiceRegistry
from cognitive_runtime.decisions.engine import DefaultDecisionEngine
from cognitive_runtime.decisions.interfaces import DecisionEngine
from cognitive_runtime.decisions.policies import DeterministicRulePolicy
from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.executor import DefaultExecutor
from cognitive_runtime.executor.interfaces import Executor
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.goals.manager import InMemoryGoalManager
from cognitive_runtime.knowledge.interfaces import KnowledgeSystem
from cognitive_runtime.knowledge.networkx_repository import NetworkXGraphRepository
from cognitive_runtime.knowledge.system import KnowledgeSystemImpl
from cognitive_runtime.logging.logger import configure_logging, get_logger
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.memory.sqlite_repository import SqliteMemoryRepository
from cognitive_runtime.memory.system import MemorySystemImpl
from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.planner.planner import DefaultPlanner
from cognitive_runtime.planner.strategies import SequentialTemplateStrategy
from cognitive_runtime.queue.interfaces import ExecutionQueue
from cognitive_runtime.queue.queue import InMemoryExecutionQueue
from cognitive_runtime.rules.engine import ForwardChainingRuleEngine
from cognitive_runtime.rules.interfaces import RuleEngine
from cognitive_runtime.working_memory.interfaces import WorkingMemory
from cognitive_runtime.working_memory.policies import LRUEvictionPolicy
from cognitive_runtime.working_memory.system import DefaultWorkingMemory

logger = get_logger(__name__)


def startup(env_file: str | None = None) -> BrainCore:
    """
    Initialize the cognitive runtime.

    This function performs the following steps:
    1. Loads configuration settings.
    2. Configures structured logging.
    3. Initializes the Dependency Injection container.
    4. Registers concrete core services in the container.
    5. Starts the BrainCore orchestrator.

    Args:
        env_file: Optional path to a .env configuration file.

    Returns:
        An initialized and running BrainCore instance.
    """
    settings = load_settings(env_file)
    configure_logging(settings.logging)
    logger.info(
        "cognitive_runtime.startup",
        environment=settings.environment,
        status="starting",
    )

    container = Container()
    container.register_singleton(CognitiveSettings, settings)

    # 1. Event Bus
    event_bus = SynchronousEventBus()
    container.register_singleton(EventBus, event_bus)

    # 2. Service Registry
    registry = SynchronousServiceRegistry(event_bus)
    container.register_singleton(ServiceRegistry, registry)

    # 3. Memory System
    memory_repo = SqliteMemoryRepository(":memory:")  # Using in-memory for V0.1 default
    memory_system = MemorySystemImpl(memory_repo, event_bus)
    container.register_singleton(MemorySystem, memory_system)

    # 4. Knowledge System
    knowledge_repo = NetworkXGraphRepository()
    knowledge_system = KnowledgeSystemImpl(knowledge_repo, event_bus)
    container.register_singleton(KnowledgeSystem, knowledge_system)

    # 5. Rule Engine
    rule_engine = ForwardChainingRuleEngine(event_bus)
    container.register_singleton(RuleEngine, rule_engine)

    # 6. Goal Manager
    goal_manager = InMemoryGoalManager(event_bus)
    container.register_singleton(GoalManager, goal_manager)

    # 7. Working Memory
    eviction_policy = LRUEvictionPolicy()
    working_memory = DefaultWorkingMemory(event_bus, eviction_policy, capacity=20)
    container.register_singleton(WorkingMemory, working_memory)

    # 8. Decision Engine
    decision_policy = DeterministicRulePolicy(rule_engine)
    decision_engine = DefaultDecisionEngine(event_bus, decision_policy)
    container.register_singleton(DecisionEngine, decision_engine)

    # 9. Planner
    planner_strategy = SequentialTemplateStrategy()
    planner = DefaultPlanner(event_bus, planner_strategy)
    container.register_singleton(Planner, planner)

    # 10. Execution Queue
    execution_queue = InMemoryExecutionQueue(event_bus)
    container.register_singleton(ExecutionQueue, execution_queue)
    
    # 11. Executor
    executor = DefaultExecutor(execution_queue, event_bus)
    container.register_singleton(Executor, executor)

    # 12. Adapters
    fs_adapter = FilesystemAdapter(event_bus)
    http_adapter = HttpAdapter(event_bus)
    process_adapter = ProcessAdapter(event_bus)
    plugin_registry = DefaultPluginRegistry()
    registry.register(PluginRegistryInterface, plugin_registry)
    plugin_adapter = PluginAdapter(event_bus, registry)
    
    executor.register_adapter(ActionType.FILE_READ, fs_adapter)
    executor.register_adapter(ActionType.FILE_WRITE, fs_adapter)
    executor.register_adapter(ActionType.FILE_DELETE, fs_adapter)
    executor.register_adapter(ActionType.HTTP_GET, http_adapter)
    executor.register_adapter(ActionType.HTTP_POST, http_adapter)
    executor.register_adapter(ActionType.PROCESS_START, process_adapter)
    executor.register_adapter(ActionType.PROCESS_STOP, process_adapter)
    executor.register_adapter(ActionType.PLUGIN_CALL, plugin_adapter)

    # 13. Result Collector
    result_collector = ResultCollector(event_bus, working_memory, memory_system)
    container.register_singleton(ResultCollector, result_collector)
    
    # 14. Execution Pipeline
    pipeline = ExecutionPipeline(
        event_bus=event_bus,
        goal_manager=goal_manager,
        decision_engine=decision_engine,
        planner=planner,
        execution_queue=execution_queue,
        executor=executor,
        result_collector=result_collector,
    )
    container.register_singleton(ExecutionPipeline, pipeline)

    brain = BrainCore(container)
    brain.start()

    logger.info("cognitive_runtime.startup", status="completed")
    return brain


def shutdown(brain: BrainCore) -> None:
    """
    Gracefully terminate the cognitive runtime via BrainCore.

    Args:
        brain: The running BrainCore instance.
    """
    logger.info("cognitive_runtime.shutdown", status="starting")

    brain.stop()

    logger.info("cognitive_runtime.shutdown", status="completed")
