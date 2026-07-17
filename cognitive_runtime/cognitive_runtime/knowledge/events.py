from typing import Any

from cognitive_runtime.events.models import Event


def create_fact_added_event(fact_id: str, source: str) -> Event:
    return Event(event_type="FactAdded", source=source, payload={"fact_id": fact_id})


def create_fact_updated_event(fact_id: str, source: str) -> Event:
    return Event(event_type="FactUpdated", source=source, payload={"fact_id": fact_id})


def create_fact_removed_event(fact_id: str, source: str) -> Event:
    return Event(event_type="FactRemoved", source=source, payload={"fact_id": fact_id})


def create_knowledge_queried_event(
    query_dict: dict[str, Any], result_count: int, source: str
) -> Event:
    return Event(
        event_type="KnowledgeQueried",
        source=source,
        payload={"query": query_dict, "result_count": result_count},
    )
