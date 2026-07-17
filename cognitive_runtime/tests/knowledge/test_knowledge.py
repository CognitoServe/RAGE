import threading

import pytest

from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.knowledge.exceptions import DuplicateFactError, FactNotFoundError
from cognitive_runtime.knowledge.models import Fact, FactQuery
from cognitive_runtime.knowledge.networkx_repository import NetworkXGraphRepository
from cognitive_runtime.knowledge.system import KnowledgeSystemImpl


@pytest.fixture
def event_bus():
    return SynchronousEventBus()


@pytest.fixture
def graph_repo():
    return NetworkXGraphRepository()


@pytest.fixture
def knowledge_system(graph_repo, event_bus):
    return KnowledgeSystemImpl(repository=graph_repo, event_bus=event_bus)


def test_add_and_get_fact(knowledge_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("FactAdded", lambda e: published_events.append(e))

    fact = Fact(subject="Paris", predicate="capital_of", object="France", source="test")
    knowledge_system.add_fact(fact)

    assert knowledge_system.exists(fact.fact_id) is True

    retrieved = knowledge_system.get_fact(fact.fact_id)
    assert retrieved == fact

    assert len(published_events) == 1
    assert published_events[0].payload["fact_id"] == fact.fact_id


def test_update_fact(knowledge_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("FactUpdated", lambda e: published_events.append(e))

    fact = Fact(subject="Battery", predicate="charge", object="15%", source="sensor")
    knowledge_system.add_fact(fact)

    # Immutable copy update
    updated_fact = fact.model_copy(update={"object": "20%", "confidence": 0.9})
    knowledge_system.update_fact(updated_fact)

    retrieved = knowledge_system.get_fact(fact.fact_id)
    assert retrieved.object == "20%"
    assert retrieved.confidence == 0.9

    assert len(published_events) == 1
    assert published_events[0].payload["fact_id"] == fact.fact_id


def test_update_fact_nodes_changed(knowledge_system):
    fact = Fact(subject="A", predicate="related_to", object="B", source="test")
    knowledge_system.add_fact(fact)

    updated_fact = fact.model_copy(update={"subject": "C", "object": "D"})
    knowledge_system.update_fact(updated_fact)

    retrieved = knowledge_system.get_fact(fact.fact_id)
    assert retrieved.subject == "C"
    assert retrieved.object == "D"

    # Old nodes A and B should be cleaned up (no neighbors)
    assert len(knowledge_system.neighbors("A")) == 0


def test_remove_fact(knowledge_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("FactRemoved", lambda e: published_events.append(e))

    fact = Fact(subject="Dog", predicate="is_a", object="Animal", source="test")
    knowledge_system.add_fact(fact)

    knowledge_system.remove_fact(fact.fact_id)

    assert knowledge_system.exists(fact.fact_id) is False
    with pytest.raises(FactNotFoundError):
        knowledge_system.get_fact(fact.fact_id)

    assert len(published_events) == 1
    assert published_events[0].payload["fact_id"] == fact.fact_id


def test_find_facts(knowledge_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("KnowledgeQueried", lambda e: published_events.append(e))

    fact1 = Fact(subject="Dog", predicate="is_a", object="Animal", source="test")
    fact2 = Fact(subject="Cat", predicate="is_a", object="Animal", source="test")
    fact3 = Fact(subject="Dog", predicate="has_part", object="Tail", source="test")

    knowledge_system.add_fact(fact1)
    knowledge_system.add_fact(fact2)
    knowledge_system.add_fact(fact3)

    results = knowledge_system.find(FactQuery(subject="Dog"))
    assert len(results) == 2

    results = knowledge_system.find(FactQuery(object="Animal"))
    assert len(results) == 2

    results = knowledge_system.find(FactQuery(predicate="has_part"))
    assert len(results) == 1

    assert len(published_events) == 3


def test_neighbors(knowledge_system):
    knowledge_system.add_fact(
        Fact(subject="A", predicate="to", object="B", source="test")
    )
    knowledge_system.add_fact(
        Fact(subject="C", predicate="to", object="A", source="test")
    )

    neighbors = knowledge_system.neighbors("A")
    assert "B" in neighbors
    assert "C" in neighbors
    assert len(neighbors) == 2


def test_duplicate_and_not_found(knowledge_system):
    fact = Fact(subject="X", predicate="Y", object="Z", source="test")
    knowledge_system.add_fact(fact)

    with pytest.raises(DuplicateFactError):
        knowledge_system.add_fact(fact)

    with pytest.raises(FactNotFoundError):
        knowledge_system.get_fact("invalid_id")


def test_thread_safety(knowledge_system):
    def worker(i: int):
        for j in range(20):
            fact = Fact(
                subject=f"Subj_{i}", predicate="link", object=f"Obj_{j}", source="test"
            )
            knowledge_system.add_fact(fact)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 10 workers * 20 iterations = 200 facts
    results = knowledge_system.find(FactQuery(predicate="link"))
    assert len(results) == 200


def test_update_fact_single_node_changes(knowledge_system):
    fact = Fact(subject="A", predicate="related_to", object="B", source="test")
    knowledge_system.add_fact(fact)

    # 1. Update only subject
    updated_subj = fact.model_copy(update={"subject": "C"})
    knowledge_system.update_fact(updated_subj)
    assert knowledge_system.get_fact(fact.fact_id).subject == "C"
    assert "A" not in knowledge_system.neighbors("C")
    assert len(knowledge_system.neighbors("A")) == 0

    # 2. Update only object
    updated_obj = updated_subj.model_copy(update={"object": "D"})
    knowledge_system.update_fact(updated_obj)
    assert knowledge_system.get_fact(fact.fact_id).object == "D"
    assert len(knowledge_system.neighbors("B")) == 0


def test_degree_safeguards(knowledge_system):
    # Tests that nodes with degree > 0 are NOT removed during update/remove
    fact1 = Fact(subject="A", predicate="to", object="B", source="test")
    fact2 = Fact(subject="A", predicate="to", object="C", source="test")
    fact3 = Fact(subject="D", predicate="to", object="B", source="test")

    knowledge_system.add_fact(fact1)
    knowledge_system.add_fact(fact2)
    knowledge_system.add_fact(fact3)

    # 1. Update fact1: object changes to E.
    # Node A still has fact2 (A -> C), so A should not be removed.
    # Node B still has fact3 (D -> B), so B should not be removed.
    updated_fact1 = fact1.model_copy(update={"object": "E"})
    knowledge_system.update_fact(updated_fact1)

    assert "C" in knowledge_system.neighbors("A")
    assert "E" in knowledge_system.neighbors("A")
    assert "B" in knowledge_system.neighbors("D")
    assert "B" in knowledge_system._repository._graph

    # 2. Remove fact2.
    # Node A still has updated_fact1 (A -> E), so A should not be removed.
    knowledge_system.remove_fact(fact2.fact_id)
    assert "E" in knowledge_system.neighbors("A")

    # 3. Remove fact3.
    # Node B no longer has any facts (both A -> B and D -> B are gone).
    # B should be completely removed from internal graph.
    knowledge_system.remove_fact(fact3.fact_id)
    assert len(knowledge_system.neighbors("B")) == 0
    assert "B" not in knowledge_system._repository._graph


def test_find_by_source_and_confidence(knowledge_system):
    fact1 = Fact(
        subject="A", predicate="to", object="B", source="source_1", confidence=0.8
    )
    fact2 = Fact(
        subject="B", predicate="to", object="C", source="source_2", confidence=0.4
    )

    knowledge_system.add_fact(fact1)
    knowledge_system.add_fact(fact2)

    # Search by source
    res_src = knowledge_system.find(FactQuery(source="source_1"))
    assert len(res_src) == 1
    assert res_src[0].subject == "A"

    # Search by min_confidence
    res_conf = knowledge_system.find(FactQuery(min_confidence=0.5))
    assert len(res_conf) == 1
    assert res_conf[0].subject == "A"
