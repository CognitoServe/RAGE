from cognitive_runtime.core.registry.registry import SynchronousServiceRegistry
from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.knowledge.models import Fact
from cognitive_runtime.knowledge.networkx_repository import NetworkXGraphRepository
from cognitive_runtime.knowledge.system import KnowledgeSystemImpl
from cognitive_runtime.memory.models import Experience
from cognitive_runtime.memory.sqlite_repository import SqliteMemoryRepository
from cognitive_runtime.memory.system import MemorySystemImpl


# 1. Event Publish
def setup_event_publish():
    bus = SynchronousEventBus()
    bus.subscribe("TestEvent", lambda _e: None)
    return bus


def target_event_publish(bus):
    event = Event(event_type="TestEvent", source="bench")
    bus.publish(event)


# 2. Memory Insert
def setup_memory_insert():
    repo = SqliteMemoryRepository(":memory:")
    bus = SynchronousEventBus()
    system = MemorySystemImpl(repo, bus)
    return system


def target_memory_insert(system):
    exp = Experience(source="bench", category="insert")
    system.remember(exp)


# 3. Memory Lookup
def setup_memory_lookup():
    repo = SqliteMemoryRepository(":memory:")
    bus = SynchronousEventBus()
    system = MemorySystemImpl(repo, bus)
    exp = Experience(source="bench", category="lookup")
    system.remember(exp)
    return system, exp.memory_id


def target_memory_lookup(ctx):
    system, memory_id = ctx
    system.recall(memory_id)


# 4. Knowledge Insert
def setup_knowledge_insert():
    repo = NetworkXGraphRepository()
    bus = SynchronousEventBus()
    system = KnowledgeSystemImpl(repo, bus)
    return system


def target_knowledge_insert(system):
    fact = Fact(
        subject="EntityA", predicate="relates_to", object="EntityB", source="bench"
    )
    system.add_fact(fact)


# 5. Knowledge Lookup
def setup_knowledge_lookup():
    repo = NetworkXGraphRepository()
    bus = SynchronousEventBus()
    system = KnowledgeSystemImpl(repo, bus)
    fact = Fact(
        subject="EntityA", predicate="relates_to", object="EntityB", source="bench"
    )
    system.add_fact(fact)
    return system, fact.fact_id


def target_knowledge_lookup(ctx):
    system, fact_id = ctx
    system.get_fact(fact_id)


# 6. Neighbor Traversal
def setup_neighbor_traversal():
    repo = NetworkXGraphRepository()
    bus = SynchronousEventBus()
    system = KnowledgeSystemImpl(repo, bus)
    system.add_fact(Fact(subject="A", predicate="relates", object="B", source="bench"))
    system.add_fact(Fact(subject="A", predicate="relates", object="C", source="bench"))
    system.add_fact(Fact(subject="D", predicate="relates", object="A", source="bench"))
    return system


def target_neighbor_traversal(system):
    system.neighbors("A")


# 7. Service Registry Lookup
class DummyService:
    pass


def setup_registry_lookup():
    bus = SynchronousEventBus()
    registry = SynchronousServiceRegistry(bus)
    registry.register(DummyService, DummyService())
    return registry, DummyService


def target_registry_lookup(ctx):
    registry, service_class = ctx
    registry.get(service_class)
