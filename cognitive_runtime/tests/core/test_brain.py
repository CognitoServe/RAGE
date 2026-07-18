import pytest

from cognitive_runtime.config.settings import CognitiveSettings
from cognitive_runtime.core.brain import BrainCore
from cognitive_runtime.core.container import Container
from cognitive_runtime.core.models import RuntimeState
from cognitive_runtime.core.registry.interfaces import ServiceRegistry
from cognitive_runtime.decisions.interfaces import DecisionEngine
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.knowledge.interfaces import KnowledgeSystem
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.rules.interfaces import RuleEngine
from cognitive_runtime.working_memory.interfaces import WorkingMemory


from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.executor.interfaces import Executor
from cognitive_runtime.queue.interfaces import ExecutionQueue
from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.core.pipeline import ExecutionPipeline


class DummyEventBus:
    def __init__(self):
        self.published = []
        
    def publish(self, event):
        self.published.append(event)
        
    def subscribe(self, event_type, handler): pass
    def unsubscribe(self, event_type, handler): pass
    
    def shutdown(self):
        self.is_shutdown = True


class DummyRegistry:
    def __init__(self):
        self.registered = {}
        
    def register(self, interface, instance):
        self.registered[interface] = instance
        
    def unregister(self, interface):
        del self.registered[interface]
        
    def get(self, interface):
        return self.registered[interface]


class DummyMemory:
    def __init__(self):
        self.is_shutdown = False
    
    def shutdown(self):
        self.is_shutdown = True

class DummyKnowledge: pass
class DummyRuleEngine: pass
class DummyGoalManager: pass
class DummyWorkingMemory: pass
class DummyDecisionEngine: pass
class DummyPlanner: pass
class DummyExecutor:
    def start(self): pass
    def shutdown(self): pass
class DummyQueue: pass
class DummyCollector: pass
class DummyPipeline: pass


def setup_container():
    container = Container()
    container.register_singleton(CognitiveSettings, CognitiveSettings())
    container.register_singleton(EventBus, DummyEventBus())
    container.register_singleton(ServiceRegistry, DummyRegistry())
    container.register_singleton(MemorySystem, DummyMemory())
    container.register_singleton(KnowledgeSystem, DummyKnowledge())
    container.register_singleton(RuleEngine, DummyRuleEngine())
    container.register_singleton(GoalManager, DummyGoalManager())
    container.register_singleton(WorkingMemory, DummyWorkingMemory())
    container.register_singleton(DecisionEngine, DummyDecisionEngine())
    container.register_singleton(Planner, DummyPlanner())
    container.register_singleton(Executor, DummyExecutor())
    container.register_singleton(ExecutionQueue, DummyQueue())
    container.register_singleton(ResultCollector, DummyCollector())
    container.register_singleton(ExecutionPipeline, DummyPipeline())
    return container


def test_brain_startup():
    container = setup_container()
    brain = BrainCore(container)
    
    assert brain.status() == RuntimeState.STOPPED
    
    brain.start()
    assert brain.status() == RuntimeState.RUNNING
    
    # Check if services were registered
    registry = container.resolve(ServiceRegistry)
    assert EventBus in registry.registered
    assert MemorySystem in registry.registered
    assert KnowledgeSystem in registry.registered
    assert RuleEngine in registry.registered
    assert GoalManager in registry.registered
    assert WorkingMemory in registry.registered
    assert DecisionEngine in registry.registered
    
    # Check events published
    bus = container.resolve(EventBus)
    assert any(e.event_type == "RuntimeStarted" for e in bus.published)


def test_brain_shutdown():
    container = setup_container()
    brain = BrainCore(container)
    brain.start()
    
    brain.stop()
    assert brain.status() == RuntimeState.STOPPED
    
    bus = container.resolve(EventBus)
    assert any(e.event_type == "RuntimeStopping" for e in bus.published)
    assert any(e.event_type == "RuntimeStopped" for e in bus.published)
    # Check shutdown on services
    assert getattr(bus, "is_shutdown", False)
    
    memory = container.resolve(MemorySystem)
    assert getattr(memory, "is_shutdown", False)

def test_brain_shutdown_no_shutdown_method():
    # Test for EventBus without shutdown method
    class NoShutdownBus:
        def publish(self, event): pass
        def subscribe(self, event_type, handler): pass
        def unsubscribe(self, event_type, handler): pass
        
    container = setup_container()
    container.register_singleton(EventBus, NoShutdownBus())
    
    brain = BrainCore(container)
    brain.start()
    brain.stop() # Should not raise exception
    
    assert brain.status() == RuntimeState.STOPPED


def test_brain_restart():
    container = setup_container()
    brain = BrainCore(container)
    
    brain.start()
    assert brain.status() == RuntimeState.RUNNING
    
    brain.restart()
    assert brain.status() == RuntimeState.RUNNING
    
    bus = container.resolve(EventBus)
    # Should have started, stopped, started
    started = [e for e in bus.published if e.event_type == "RuntimeStarted"]
    stopped = [e for e in bus.published if e.event_type == "RuntimeStopped"]
    assert len(started) == 2
    assert len(stopped) == 1


def test_brain_missing_dependency():
    container = Container()
    # Missing everything
    brain = BrainCore(container)
    
    with pytest.raises(KeyError):
        brain.start()
        
    assert brain.status() == RuntimeState.ERROR


def test_brain_health():
    container = setup_container()
    brain = BrainCore(container)
    
    health = brain.health()
    assert health.state == RuntimeState.STOPPED
    assert health.services == {}
    
    brain.start()
    health = brain.health()
    assert health.state == RuntimeState.RUNNING
    assert "EventBus" in health.services
    assert health.services["EventBus"] == "OK"
