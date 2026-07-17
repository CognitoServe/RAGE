import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem
from cognitive_runtime.working_memory.policies import LRUEvictionPolicy
from cognitive_runtime.working_memory.system import DefaultWorkingMemory


class DummyEventBus(EventBus):
    def __init__(self):
        self.published = []
        
    def publish(self, event):
        self.published.append(event)
        
    def subscribe(self, event_type, handler): pass
    def unsubscribe(self, event_type, handler): pass

@pytest.fixture
def memory():
    bus = DummyEventBus()
    policy = LRUEvictionPolicy()
    wm = DefaultWorkingMemory(bus, policy, capacity=3)
    return wm, bus

def test_activate_and_contains(memory):
    wm, bus = memory
    item = WorkingMemoryItem(item_id="1", source=ItemSource.MEMORY, reference_id="ref1")
    
    wm.activate(item)
    assert wm.contains("1") is True
    assert wm.contains("2") is False
    
    events = [e for e in bus.published if e.event_type == "WorkingMemoryActivated"]
    assert len(events) == 1

def test_deactivate(memory):
    wm, bus = memory
    item = WorkingMemoryItem(item_id="1", source=ItemSource.MEMORY, reference_id="ref1")
    wm.activate(item)
    
    wm.deactivate("1")
    assert wm.contains("1") is False
    
    events = [e for e in bus.published if e.event_type == "WorkingMemoryDeactivated"]
    assert len(events) == 1

def test_capacity_and_eviction(memory):
    wm, bus = memory
    # Capacity is 3
    i1 = WorkingMemoryItem(item_id="1", source=ItemSource.MEMORY, reference_id="r1")
    i2 = WorkingMemoryItem(item_id="2", source=ItemSource.MEMORY, reference_id="r2")
    i3 = WorkingMemoryItem(item_id="3", source=ItemSource.MEMORY, reference_id="r3")
    
    wm.activate(i1)
    time.sleep(0.01) # Ensure time difference
    wm.activate(i2)
    time.sleep(0.01)
    wm.activate(i3)
    
    assert len(wm.active_items()) == 3
    
    # Access i1 so it's not the LRU
    wm.contains("1")
    
    # Now LRU should be i2
    i4 = WorkingMemoryItem(item_id="4", source=ItemSource.MEMORY, reference_id="r4")
    wm.activate(i4)
    
    # Capacity should still be 3
    assert len(wm.active_items()) == 3
    assert wm.contains("2") is False # i2 was evicted
    assert wm.contains("1") is True
    assert wm.contains("3") is True
    assert wm.contains("4") is True
    
    events = [e for e in bus.published if e.event_type == "WorkingMemoryEvicted"]
    assert len(events) == 1
    assert events[0].payload["item_id"] == "2"

def test_passive_ttl(memory):
    wm, bus = memory
    
    # Item with TTL of -1 (already expired)
    # Actually let's simulate expiration by making inserted_at old
    old_time = datetime.now(UTC) - timedelta(seconds=10)
    item = WorkingMemoryItem(
        item_id="1", 
        source=ItemSource.MEMORY, 
        reference_id="r1",
        ttl=5,
        inserted_at=old_time,
        last_accessed=old_time
    )
    
    wm.activate(item)
    
    # When checking contains, it should notice TTL expired, remove it, and return False
    assert wm.contains("1") is False
    
    events = [e for e in bus.published if e.event_type == "WorkingMemoryDeactivated"]
    assert len(events) == 1 # Expiration acts as deactivation (or we could have a specific event, but RFC doesn't mention expired event, only deactivated or evicted)

def test_clear(memory):
    wm, bus = memory
    wm.activate(WorkingMemoryItem(item_id="1", source=ItemSource.MEMORY, reference_id="r1"))
    wm.activate(WorkingMemoryItem(item_id="2", source=ItemSource.MEMORY, reference_id="r2"))
    
    wm.clear()
    assert len(wm.active_items()) == 0
    
    events = [e for e in bus.published if e.event_type == "WorkingMemoryCleared"]
    assert len(events) == 1

def test_set_capacity(memory):
    wm, _ = memory
    assert wm.capacity() == 3
    wm.set_capacity(1)
    assert wm.capacity() == 1

def test_thread_safety(memory):
    wm, bus = memory
    wm.set_capacity(100) # Ensure no eviction mess for simple threading test
    
    def worker(i):
        item = WorkingMemoryItem(item_id=str(i), source=ItemSource.MEMORY, reference_id=str(i))
        wm.activate(item)
        wm.contains(str(i))
        if i % 2 == 0:
            wm.deactivate(str(i))
            
    threads = []
    for i in range(100):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(wm.active_items()) == 50 # 100 added, 50 removed
