import sys
import uuid
from datetime import UTC, datetime

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.decisions.models import DecisionContext
from cognitive_runtime.goals.models import Goal, GoalStatus
from cognitive_runtime.knowledge.models import Fact, FactQuery
from cognitive_runtime.rules.models import (
    Conclusion,
    FactPattern,
    Operator,
    Rule,
    RuleCondition,
)
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem


def run_e2e_pipeline():
    print("Starting E2E Cognitive Pipeline Test...")
    brain = startup()
    health = brain.health()
    
    # Extract subsystems
    # Note: the test orchestrates the pipeline since V1 Alpha does not have an autonomous orchestrator loop.
    bus = brain._services["EventBus"]
    goal_manager = brain._services["GoalManager"]
    wm = brain._services["WorkingMemory"]
    knowledge = brain._services["KnowledgeSystem"]
    rules = brain._services["RuleEngine"]
    decisions = brain._services["DecisionEngine"]
    planner = brain._services["Planner"]
    
    # Event tracking
    event_log = []
    
    def on_event(event):
        event_log.append(event)
        print(f"EVENT: {event.event_type} from {event.source}")
        
    # Subscribe to all by cheating the SynchronousEventBus (or we just subscribe to specific events)
    # The SynchronousEventBus in V1 doesn't support wildcard, but we can patch publish for tracking in test
    original_publish = bus.publish
    def tracking_publish(event):
        on_event(event)
        original_publish(event)
    bus.publish = tracking_publish

    # Pipeline Step 1: Goal Created
    goal_id = str(uuid.uuid4())
    goal = Goal(goal_id=goal_id, title="Organize Downloads", description="Organize Downloads Folder", priority=1, status=GoalStatus.ACTIVE, created_at=datetime.now(UTC), metadata={})
    goal_manager.create(goal)
    
    # Pipeline Step 2: Working Memory Activated
    wm_item = WorkingMemoryItem(item_id=f"wm_{goal_id}", source=ItemSource.GOAL, reference_id=goal_id, metadata={"context": "needs_organization"})
    wm.activate(wm_item)
    
    # Pipeline Step 3: Knowledge Retrieved
    # Actually we should store it first then retrieve it
    knowledge.add_fact(Fact(subject="DownloadsFolder", predicate="contains", object="Files", source="system"))
    facts = knowledge.find(FactQuery(subject="DownloadsFolder"))
    assert len(facts) > 0
    # Retrieving doesn't fire an event in V1 RFC, but we can verify it happened
    
    # Pipeline Step 4: Rules Evaluated
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(predicate="is_active_goal", object="true")]
        ),
        conclusion=Conclusion(name="OrganizeAction", payload={"action": "organize"})
    )
    rules.register(rule)
    
    # We evaluate facts just for the test sequence
    matched_rules = rules.evaluate(facts)

    # Pipeline Step 5: Decision Created
    context = DecisionContext(active_goals=[goal], working_memory_items=[wm_item])
    decision = decisions.decide(context)
    
    # Pipeline Step 6: Planner Generated Plan
    plan = planner.create_plan(goal_id)
    
    # Shutdown
    bus.publish = original_publish
    shutdown(brain)
    
    # Verify Sequence
    # We expect GoalCreated -> WorkingMemoryActivated -> DecisionCreated -> PlanCreated
    types = [e.event_type for e in event_log]
    expected_sequence = ["GoalCreated", "WorkingMemoryActivated", "DecisionCreated", "PlanCreated"]
    
    # Assert sequence is present in order
    idx = 0
    for e_type in types:
        if idx < len(expected_sequence) and e_type == expected_sequence[idx]:
            idx += 1
            
    if idx < len(expected_sequence):
        print(f"E2E TEST FAILED: Missing events in sequence. Found: {types}, Expected: {expected_sequence}")
        sys.exit(1)
        
    print("E2E Cognitive Pipeline Test PASSED.")
    
if __name__ == "__main__":
    run_e2e_pipeline()
