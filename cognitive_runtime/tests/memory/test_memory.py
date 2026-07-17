import threading
from datetime import UTC, datetime, timedelta

import pytest

from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.memory.models import Experience, ExperienceStatus, SearchQuery
from cognitive_runtime.memory.sqlite_repository import SqliteMemoryRepository
from cognitive_runtime.memory.system import MemorySystemImpl


@pytest.fixture
def event_bus():
    return SynchronousEventBus()


@pytest.fixture
def memory_repo():
    # Use in-memory sqlite for tests
    return SqliteMemoryRepository(":memory:")


@pytest.fixture
def memory_system(memory_repo, event_bus):
    return MemorySystemImpl(repository=memory_repo, event_bus=event_bus)


def test_remember_and_recall(memory_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("MemoryStored", lambda e: published_events.append(e))
    event_bus.subscribe("MemoryRetrieved", lambda e: published_events.append(e))

    exp = Experience(
        source="test", category="action", payload={"action": "created_folder"}
    )
    memory_system.remember(exp)

    assert len(published_events) == 1
    assert published_events[0].event_type == "MemoryStored"
    assert published_events[0].payload["memory_id"] == exp.memory_id

    recalled_exp = memory_system.recall(exp.memory_id)
    assert recalled_exp.memory_id == exp.memory_id
    assert recalled_exp.payload == {"action": "created_folder"}

    assert len(published_events) == 2
    assert published_events[1].event_type == "MemoryRetrieved"


def test_archive(memory_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("MemoryArchived", lambda e: published_events.append(e))

    exp = Experience(source="test", category="action")
    memory_system.remember(exp)

    assert memory_system.recall(exp.memory_id).status == ExperienceStatus.ACTIVE

    memory_system.archive(exp.memory_id)
    assert memory_system.recall(exp.memory_id).status == ExperienceStatus.ARCHIVED

    assert len(published_events) == 1
    assert published_events[0].event_type == "MemoryArchived"
    assert published_events[0].payload["memory_id"] == exp.memory_id


def test_search(memory_system, event_bus):
    published_events: list[Event] = []
    event_bus.subscribe("MemorySearchExecuted", lambda e: published_events.append(e))

    now = datetime.now(UTC)
    exp1 = Experience(
        source="test",
        category="A",
        tags=["tag1", "tag2"],
        timestamp=now - timedelta(hours=2),
    )
    exp2 = Experience(
        source="test", category="B", tags=["tag2"], timestamp=now - timedelta(hours=1)
    )

    memory_system.remember(exp1)
    memory_system.remember(exp2)

    # Search by category
    results = memory_system.search(SearchQuery(category="A"))
    assert len(results) == 1
    assert results[0].memory_id == exp1.memory_id

    # Search by tags
    results = memory_system.search(SearchQuery(tags=["tag2"]))
    assert len(results) == 2

    results = memory_system.search(SearchQuery(tags=["tag1", "tag2"]))
    assert len(results) == 1
    assert results[0].memory_id == exp1.memory_id

    # Search by time range
    results = memory_system.search(SearchQuery(start_time=now - timedelta(minutes=90)))
    assert len(results) == 1
    assert results[0].memory_id == exp2.memory_id

    results = memory_system.search(SearchQuery(end_time=now - timedelta(minutes=90)))
    assert len(results) == 1
    assert results[0].memory_id == exp1.memory_id

    assert len(published_events) == 5  # 5 searches
    assert published_events[0].event_type == "MemorySearchExecuted"
    assert published_events[0].payload["result_count"] == 1


def test_duplicate_ids(memory_system):
    exp = Experience(source="test", category="action")
    memory_system.remember(exp)

    with pytest.raises(ValueError, match="already exists"):
        memory_system.remember(exp)


def test_not_found(memory_system):
    with pytest.raises(KeyError):
        memory_system.recall("non_existent_id")

    with pytest.raises(KeyError):
        memory_system.archive("non_existent_id")


def test_thread_safety(memory_system):
    # Just a simple concurrent write test
    def worker():
        for _ in range(50):
            exp = Experience(source="test", category="concurrent")
            memory_system.remember(exp)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results = memory_system.search(SearchQuery(category="concurrent"))
    assert len(results) == 500
