from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_fact_added_event,
    create_fact_removed_event,
    create_fact_updated_event,
    create_knowledge_queried_event,
)
from .interfaces import GraphRepository, KnowledgeSystem
from .models import Fact, FactQuery


class KnowledgeSystemImpl(KnowledgeSystem):
    def __init__(self, repository: GraphRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
        self._source_name = "KnowledgeSystem"

    def add_fact(self, fact: Fact) -> None:
        self._repository.add(fact)
        event = create_fact_added_event(fact.fact_id, self._source_name)
        self._event_bus.publish(event)

    def update_fact(self, fact: Fact) -> None:
        self._repository.update(fact)
        event = create_fact_updated_event(fact.fact_id, self._source_name)
        self._event_bus.publish(event)

    def remove_fact(self, fact_id: str) -> None:
        self._repository.remove(fact_id)
        event = create_fact_removed_event(fact_id, self._source_name)
        self._event_bus.publish(event)

    def get_fact(self, fact_id: str) -> Fact:
        return self._repository.get(fact_id)

    def find(self, query: FactQuery) -> list[Fact]:
        results = self._repository.find(query)
        event = create_knowledge_queried_event(
            query_dict=query.model_dump(mode="json"),
            result_count=len(results),
            source=self._source_name,
        )
        self._event_bus.publish(event)
        return results

    def neighbors(self, entity_id: str) -> list[str]:
        return self._repository.get_neighbors(entity_id)

    def exists(self, fact_id: str) -> bool:
        return self._repository.exists(fact_id)
