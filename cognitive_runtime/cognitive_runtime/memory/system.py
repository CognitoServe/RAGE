from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_memory_archived_event,
    create_memory_retrieved_event,
    create_memory_search_executed_event,
    create_memory_stored_event,
)
from .interfaces import MemoryRepository, MemorySystem
from .models import Experience, ExperienceStatus, SearchQuery


class MemorySystemImpl(MemorySystem):
    def __init__(self, repository: MemoryRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
        self._source_name = "MemorySystem"

    def remember(self, experience: Experience) -> None:
        self._repository.save(experience)
        event = create_memory_stored_event(experience.memory_id, self._source_name)
        self._event_bus.publish(event)

    def recall(self, memory_id: str) -> Experience:
        experience = self._repository.get(memory_id)
        event = create_memory_retrieved_event(memory_id, self._source_name)
        self._event_bus.publish(event)
        return experience

    def search(self, query: SearchQuery) -> list[Experience]:
        results = self._repository.search(query)
        event = create_memory_search_executed_event(
            query_dict=query.model_dump(mode="json"),
            result_count=len(results),
            source=self._source_name,
        )
        self._event_bus.publish(event)
        return results

    def archive(self, memory_id: str) -> None:
        self._repository.update_status(memory_id, ExperienceStatus.ARCHIVED)
        event = create_memory_archived_event(memory_id, self._source_name)
        self._event_bus.publish(event)
