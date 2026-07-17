import threading

import pytest

from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.goals.exceptions import (
    DuplicateGoalError,
    GoalNotFoundError,
    InvalidStateTransitionError,
)
from cognitive_runtime.goals.manager import InMemoryGoalManager
from cognitive_runtime.goals.models import Goal, GoalStatus


class DummyEventBus(EventBus):
    def __init__(self):
        self.published = []
        
    def publish(self, event):
        self.published.append(event)
        
    def subscribe(self, event_type, handler): pass
    def unsubscribe(self, event_type, handler): pass

@pytest.fixture
def manager():
    bus = DummyEventBus()
    return InMemoryGoalManager(bus), bus

def test_create_goal(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test Goal", description="Description")
    
    mgr.create(goal)
    
    goals = mgr.list()
    assert len(goals) == 1
    assert goals[0].goal_id == "g1"
    
    # Event should be published
    assert len(bus.published) == 1
    assert bus.published[0].event_type == "GoalCreated"
    assert bus.published[0].payload["goal_id"] == "g1"

def test_create_duplicate_goal(manager):
    mgr, bus = manager
    goal1 = Goal(goal_id="g1", title="G1", description="D1")
    goal2 = Goal(goal_id="g1", title="G2", description="D2")
    
    mgr.create(goal1)
    with pytest.raises(DuplicateGoalError):
        mgr.create(goal2)

def test_update_goal(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test", description="Desc")
    mgr.create(goal)
    
    # Update title
    updated = goal.model_copy(update={"title": "New Title"})
    mgr.update(updated)
    
    goals = mgr.list()
    assert goals[0].title == "New Title"
    
    events = [e for e in bus.published if e.event_type == "GoalUpdated"]
    assert len(events) == 1

def test_update_missing_goal(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test", description="Desc")
    with pytest.raises(GoalNotFoundError):
        mgr.update(goal)

def test_invalid_state_transition(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test", description="Desc", status=GoalStatus.COMPLETED)
    mgr.create(goal)  # Can create in any state technically, or we assume CREATED
    
    # If it's already COMPLETED, transitioning back to ACTIVE should fail
    updated = goal.model_copy(update={"status": GoalStatus.ACTIVE})
    with pytest.raises(InvalidStateTransitionError):
        mgr.update(updated)

def test_complete_goal(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test", description="Desc", status=GoalStatus.ACTIVE)
    mgr.create(goal)
    
    mgr.complete("g1")
    
    # Completed goals might still be in the list, but their status is COMPLETED
    # Depending on list() implementation (active vs all). The RFC says:
    # "list(): Returns all currently tracked active goals."
    # Let's assume list() returns ALL goals, or only non-terminal.
    # We will enforce list() returns all, but we can filter by status.
    # The prompt: list() - maybe all? Wait, the RFC says "Query active goals" as a responsibility, 
    # but the API is list(). Let's assume list() returns all.
    goals = [g for g in mgr.list() if g.goal_id == "g1"]
    assert goals[0].status == GoalStatus.COMPLETED
    
    events = [e for e in bus.published if e.event_type == "GoalCompleted"]
    assert len(events) == 1

def test_cancel_goal(manager):
    mgr, bus = manager
    goal = Goal(goal_id="g1", title="Test", description="Desc")
    mgr.create(goal)
    
    mgr.cancel("g1")
    
    goals = [g for g in mgr.list() if g.goal_id == "g1"]
    assert goals[0].status == GoalStatus.CANCELLED
    
    events = [e for e in bus.published if e.event_type == "GoalCancelled"]
    assert len(events) == 1

def test_priority_ordering(manager):
    mgr, bus = manager
    mgr.create(Goal(goal_id="g1", title="G1", description="D1", priority=10, status=GoalStatus.ACTIVE))
    mgr.create(Goal(goal_id="g2", title="G2", description="D2", priority=50, status=GoalStatus.ACTIVE))
    mgr.create(Goal(goal_id="g3", title="G3", description="D3", priority=30, status=GoalStatus.ACTIVE))
    
    highest = mgr.highest_priority()
    assert highest.goal_id == "g2"
    
    # If g2 is completed, the next highest is g3
    mgr.complete("g2")
    highest = mgr.highest_priority()
    assert highest.goal_id == "g3"

def test_parent_child_goals(manager):
    mgr, bus = manager
    mgr.create(Goal(goal_id="p1", title="Parent", description="Parent"))
    mgr.create(Goal(goal_id="c1", title="Child", description="Child", parent_goal="p1"))
    
    goals = mgr.list()
    assert len(goals) == 2
    child = next(g for g in goals if g.goal_id == "c1")
    assert child.parent_goal == "p1"

def test_thread_safety(manager):
    mgr, bus = manager
    def worker(i):
        goal = Goal(goal_id=f"g{i}", title=f"G{i}", description="D")
        mgr.create(goal)
        mgr.update(goal.model_copy(update={"priority": i}))
        if i % 2 == 0:
            mgr.complete(f"g{i}")
        else:
            mgr.cancel(f"g{i}")

    threads = []
    for i in range(100):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(mgr.list()) == 100
    # Also check if events are published correctly (100 created, 100 updated, 100 terminal)
    # Total events: 300 (or more if priority change events are published)
    assert len(bus.published) >= 300
