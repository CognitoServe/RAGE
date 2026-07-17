import threading
from datetime import UTC, datetime

from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_wm_activated_event,
    create_wm_cleared_event,
    create_wm_deactivated_event,
    create_wm_evicted_event,
)
from .interfaces import EvictionPolicy, WorkingMemory
from .models import WorkingMemoryItem


class DefaultWorkingMemory(WorkingMemory):
    """
    Default thread-safe implementation of Working Memory.
    """

    def __init__(
        self, event_bus: EventBus, eviction_policy: EvictionPolicy, capacity: int = 20
    ):
        self._bus = event_bus
        self._policy = eviction_policy
        self._capacity = capacity
        self._items: dict[str, WorkingMemoryItem] = {}
        self._lock = threading.RLock()

    def _is_expired(self, item: WorkingMemoryItem) -> bool:
        if item.ttl is None:
            return False
        age = (datetime.now(UTC) - item.inserted_at).total_seconds()
        return age >= item.ttl

    def _passive_expiration_check(self) -> None:
        """Removes expired items. Requires lock."""
        expired_ids = []
        for item in self._items.values():
            if self._is_expired(item):
                expired_ids.append(item.item_id)

        for item_id in expired_ids:
            del self._items[item_id]
            self._bus.publish(
                create_wm_deactivated_event(item_id, source="WorkingMemoryTTL")
            )

    def activate(self, item: WorkingMemoryItem) -> None:
        with self._lock:
            self._passive_expiration_check()

            # If it's a new item and we're at capacity, we need to evict
            if item.item_id not in self._items and len(self._items) >= self._capacity:
                self._evict()

            # Defensive copy and update last accessed
            new_item = item.model_copy(
                deep=True, update={"last_accessed": datetime.now(UTC)}
            )
            self._items[item.item_id] = new_item

        self._bus.publish(create_wm_activated_event(item.item_id))

    def _evict(self) -> None:
        """Evicts an item based on the eviction policy. Requires lock."""
        if not self._items:
            return

        to_evict = self._policy.select_eviction(list(self._items.values()))
        if to_evict and to_evict.item_id in self._items:
            del self._items[to_evict.item_id]
            self._bus.publish(create_wm_evicted_event(to_evict.item_id))

    def deactivate(self, item_id: str) -> None:
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                self._bus.publish(create_wm_deactivated_event(item_id))

    def contains(self, item_id: str) -> bool:
        with self._lock:
            self._passive_expiration_check()
            if item_id in self._items:
                # Update access time
                item = self._items[item_id]
                updated = item.model_copy(update={"last_accessed": datetime.now(UTC)})
                self._items[item_id] = updated
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
        self._bus.publish(create_wm_cleared_event())

    def active_items(self) -> list[WorkingMemoryItem]:
        with self._lock:
            self._passive_expiration_check()
            return [i.model_copy(deep=True) for i in self._items.values()]

    def capacity(self) -> int:
        with self._lock:
            return self._capacity

    def set_capacity(self, limit: int) -> None:
        with self._lock:
            self._capacity = limit
            # If new limit is smaller than current size, evict until we fit
            self._passive_expiration_check()
            while len(self._items) > self._capacity:
                self._evict()
