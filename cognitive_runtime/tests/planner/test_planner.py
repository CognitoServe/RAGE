import threading
from typing import Any

import pytest

from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.planner.exceptions import (
    PlanNotFoundError,
)
from cognitive_runtime.planner.models import PlanStatus, StepStatus
from cognitive_runtime.planner.planner import DefaultPlanner
from cognitive_runtime.planner.strategies import SequentialTemplateStrategy


class SynchronousEventBus(EventBus):
    def __init__(self):
        self.published = []
    def subscribe(self, event_type: str, handler: Any) -> None: pass
    def unsubscribe(self, event_type: str, handler: Any) -> None: pass
    def publish(self, event) -> None:
        self.published.append(event)

@pytest.fixture
def planner_setup():
    bus = SynchronousEventBus()
    strategy = SequentialTemplateStrategy()
    planner = DefaultPlanner(bus, strategy)
    return planner, bus

def test_create_plan(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    assert plan.goal_id == "goal_123"
    assert plan.status == PlanStatus.ACTIVE
    assert len(plan.steps) == 3
    
    events = [e for e in bus.published if e.event_type == "PlanCreated"]
    assert len(events) == 1
    assert events[0].payload["plan_id"] == plan.plan_id

def test_next_and_current_step(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    # First step
    step1 = planner.next_step(plan.plan_id)
    assert step1 is not None
    assert step1.status == StepStatus.ACTIVE
    
    current = planner.current_step(plan.plan_id)
    assert current is not None
    assert current.step_id == step1.step_id
    
    # Next step should return the next pending step
    step2 = planner.next_step(plan.plan_id)
    assert step2 is not None
    assert step2.step_id != step1.step_id
    assert step2.status == StepStatus.ACTIVE

def test_mark_complete_success(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    # Complete all 3 steps
    for _ in range(3):
        step = planner.next_step(plan.plan_id)
        planner.mark_complete(plan.plan_id, step.step_id, success=True)
        
    final_plan = planner.plan_status(plan.plan_id)
    assert final_plan.status == PlanStatus.COMPLETED
    assert all(s.status == StepStatus.COMPLETED for s in final_plan.steps)
    
    completed_events = [e for e in bus.published if e.event_type == "PlanCompleted"]
    assert len(completed_events) == 1

def test_mark_complete_failure(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    step = planner.next_step(plan.plan_id)
    planner.mark_complete(plan.plan_id, step.step_id, success=False)
    
    final_plan = planner.plan_status(plan.plan_id)
    assert final_plan.status == PlanStatus.FAILED
    
    # The step itself should be failed
    assert final_plan.steps[0].status == StepStatus.FAILED
    
    failed_events = [e for e in bus.published if e.event_type == "StepFailed"]
    assert len(failed_events) == 1

def test_cancel_plan(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    planner.cancel_plan(plan.plan_id)
    
    final_plan = planner.plan_status(plan.plan_id)
    assert final_plan.status == PlanStatus.CANCELLED
    # All pending/active steps become failed when plan is cancelled
    assert all(s.status == StepStatus.FAILED for s in final_plan.steps)
    
    cancel_events = [e for e in bus.published if e.event_type == "PlanCancelled"]
    assert len(cancel_events) == 1

def test_not_found_errors(planner_setup):
    planner, bus = planner_setup
    with pytest.raises(PlanNotFoundError):
        planner.next_step("invalid_id")
        
    with pytest.raises(PlanNotFoundError):
        planner.mark_complete("invalid_id", "step_id")
        
    with pytest.raises(PlanNotFoundError):
        planner.cancel_plan("invalid_id")

def test_thread_safety(planner_setup):
    planner, bus = planner_setup
    plan = planner.create_plan("goal_123")
    
    def worker():
        try:
            step = planner.next_step(plan.plan_id)
            if step:
                planner.mark_complete(plan.plan_id, step.step_id)
        except Exception:
            pass

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    # At least some steps should be completed. 
    # Because there are only 3 steps, they should all be completed if threads caught them.
    final_plan = planner.plan_status(plan.plan_id)
    assert final_plan.status == PlanStatus.COMPLETED

def test_replanning(planner_setup):
    planner, bus = planner_setup
    
    # Simulate a failed first attempt
    first_plan = planner.create_plan("goal_123")
    first_step = planner.next_step(first_plan.plan_id)
    planner.mark_complete(first_plan.plan_id, first_step.step_id, success=False)
    
    assert planner.plan_status(first_plan.plan_id).status == PlanStatus.FAILED
    
    # Replan for the same goal
    second_plan = planner.create_plan("goal_123")
    assert second_plan.plan_id != first_plan.plan_id
    assert second_plan.goal_id == "goal_123"
    assert second_plan.status == PlanStatus.ACTIVE
    
    # We should be able to execute the new plan
    step = planner.next_step(second_plan.plan_id)
    assert step is not None
    assert step.status == StepStatus.ACTIVE
    planner.mark_complete(second_plan.plan_id, step.step_id, success=True)
    
    second_plan_status = planner.plan_status(second_plan.plan_id)
    assert second_plan_status.steps[0].status == StepStatus.COMPLETED
