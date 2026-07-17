from typing import Any

from cognitive_runtime.events.models import Event


def create_memory_stored_event(memory_id: str, source: str) -> Event:
    return Event(
        event_type="MemoryStored", source=source, payload={"memory_id": memory_id}
    )


def create_memory_archived_event(memory_id: str, source: str) -> Event:
    return Event(
        event_type="MemoryArchived", source=source, payload={"memory_id": memory_id}
    )


def create_memory_retrieved_event(memory_id: str, source: str) -> Event:
    return Event(
        event_type="MemoryRetrieved", source=source, payload={"memory_id": memory_id}
    )


def create_memory_search_executed_event(
    query_dict: dict[str, Any], result_count: int, source: str
) -> Event:
    return Event(
        event_type="MemorySearchExecuted",
        source=source,
        payload={"query": query_dict, "result_count": result_count},
    )
