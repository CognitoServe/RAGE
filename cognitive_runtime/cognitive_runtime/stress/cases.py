import os
import tempfile
import threading

from cognitive_runtime.core.registry.registry import SynchronousServiceRegistry
from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.knowledge.models import Fact, FactQuery
from cognitive_runtime.knowledge.networkx_repository import NetworkXGraphRepository
from cognitive_runtime.knowledge.system import KnowledgeSystemImpl
from cognitive_runtime.memory.models import Experience, SearchQuery
from cognitive_runtime.memory.sqlite_repository import SqliteMemoryRepository
from cognitive_runtime.memory.system import MemorySystemImpl

from .exceptions import StressTestFailureError


# 1. Event Bus Stress
def stress_event_bus(threads_count=5, iterations=1000):
    bus = SynchronousEventBus()
    exceptions = []

    def worker(tid):
        try:
            handler = lambda _e: None
            bus.subscribe(f"Topic_{tid}", handler)

            for i in range(iterations):
                bus.publish(Event(event_type=f"Topic_{tid}", source=f"worker_{tid}"))
                other_tid = (tid + 1) % threads_count
                bus.publish(
                    Event(event_type=f"Topic_{other_tid}", source=f"worker_{tid}")
                )

                if i % 100 == 0:
                    bus.unsubscribe(f"Topic_{tid}", handler)
                    bus.subscribe(f"Topic_{tid}", handler)
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Event Bus stress failed: {exceptions}")


# 2. Memory Stress
def stress_memory(threads_count=5, iterations=1000):
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    exceptions = []
    try:
        repo = SqliteMemoryRepository(temp_db_path)
        bus = SynchronousEventBus()
        system = MemorySystemImpl(repo, bus)

        for i in range(10):
            system.remember(Experience(source="init", category="test"))

        def worker(tid):
            try:
                for i in range(iterations):
                    exp = Experience(source=f"worker_{tid}", category="stress")
                    system.remember(exp)
                    system.recall(exp.memory_id)
                    system.search(SearchQuery(category="stress"))
            except Exception as e:
                exceptions.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(threads_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except OSError:
            pass

    if exceptions:
        raise StressTestFailureError(f"Memory stress failed: {exceptions}")


# 3. Knowledge Stress
def stress_knowledge(threads_count=5, iterations=1000):
    repo = NetworkXGraphRepository()
    bus = SynchronousEventBus()
    system = KnowledgeSystemImpl(repo, bus)
    exceptions = []

    system.add_fact(
        Fact(subject="Base", predicate="connects", object="Target", source="init")
    )

    def worker(tid):
        try:
            for i in range(iterations):
                fact = Fact(
                    subject=f"Node_{tid}_{i}",
                    predicate="stress_link",
                    object="Base",
                    source=f"worker_{tid}",
                )
                system.add_fact(fact)
                system.get_fact(fact.fact_id)
                system.find(FactQuery(subject=f"Node_{tid}_{i}"))
                system.neighbors("Base")

                if i % 10 == 0:
                    system.remove_fact(fact.fact_id)
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Knowledge stress failed: {exceptions}")


# 4. Service Registry Stress
def stress_registry(threads_count=5, iterations=1000):
    bus = SynchronousEventBus()
    registry = SynchronousServiceRegistry(bus)
    exceptions = []

    classes = []
    for tid in range(threads_count):

        class LocalService:
            pass

        classes.append(LocalService)

    def worker(tid):
        service_class = classes[tid]
        try:
            for i in range(iterations):
                service_instance = service_class()
                registry.register(service_class, service_instance)
                registry.get(service_class)
                registry.unregister(service_class)
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Service Registry stress failed: {exceptions}")


# 5. Rule Engine Stress
def stress_rule_engine(threads_count=5, iterations=1000):
    from cognitive_runtime.rules.engine import ForwardChainingRuleEngine
    from cognitive_runtime.rules.models import (
        Conclusion,
        FactPattern,
        Operator,
        Rule,
        RuleCondition,
    )

    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    exceptions = []

    def worker(tid):
        try:
            for i in range(iterations):
                rule = Rule(
                    rule_id=f"rule_{tid}_{i}",
                    condition=RuleCondition(
                        operator=Operator.AND,
                        patterns=[FactPattern(subject=f"Subj_{tid}_{i}")],
                    ),
                    conclusion=Conclusion(name=f"Conclusion_{tid}_{i}"),
                )
                engine.register(rule)

                if i % 10 == 0:
                    facts = [
                        Fact(
                            subject=f"Subj_{tid}_{i}",
                            predicate="is",
                            object="A",
                            source="stress",
                        )
                    ]
                    engine.evaluate(facts)
                    engine.remove(rule.rule_id)
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Rule Engine stress failed: {exceptions}")


# 6. Goal Manager Stress
def stress_goal_manager(threads_count=5, iterations=1000):
    from cognitive_runtime.goals.manager import InMemoryGoalManager
    from cognitive_runtime.goals.models import Goal

    bus = SynchronousEventBus()
    manager = InMemoryGoalManager(bus)
    exceptions = []

    def worker(tid):
        try:
            for i in range(iterations):
                goal_id = f"goal_{tid}_{i}"
                goal = Goal(
                    goal_id=goal_id,
                    title=f"G_{tid}_{i}",
                    description="Desc",
                    priority=i,
                )
                manager.create(goal)

                # Retrieve and update
                if i % 2 == 0:
                    updated = goal.model_copy(update={"priority": i + 10})
                    manager.update(updated)

                # Terminal transitions
                if i % 3 == 0:
                    manager.complete(goal_id)
                elif i % 4 == 0:
                    manager.cancel(goal_id)

                manager.highest_priority()

        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Goal Manager stress failed: {exceptions}")


# 7. Working Memory Stress
def stress_working_memory(threads_count=5, iterations=1000):
    from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem
    from cognitive_runtime.working_memory.policies import LRUEvictionPolicy
    from cognitive_runtime.working_memory.system import DefaultWorkingMemory

    bus = SynchronousEventBus()
    policy = LRUEvictionPolicy()
    wm = DefaultWorkingMemory(bus, policy, capacity=20)
    exceptions = []

    def worker(tid):
        try:
            for i in range(iterations):
                item_id = f"item_{tid}_{i}"
                item = WorkingMemoryItem(
                    item_id=item_id, source=ItemSource.MEMORY, reference_id="ref"
                )
                wm.activate(item)

                # Retrieve
                if i % 2 == 0:
                    wm.contains(item_id)

                # Active items check
                if i % 10 == 0:
                    wm.active_items()

                # Deactivate early sometimes
                if i % 3 == 0:
                    wm.deactivate(item_id)

        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Working Memory stress failed: {exceptions}")
