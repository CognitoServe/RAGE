import sys

from cognitive_runtime.core.events import (
    create_runtime_started_event,
    create_runtime_stopped_event,
    create_runtime_stopping_event,
)
from cognitive_runtime.decisions.events import (
    create_decision_created_event,
    create_decision_explained_event,
    create_decision_rejected_event,
)
from cognitive_runtime.goals.events import (
    create_goal_cancelled_event,
    create_goal_completed_event,
    create_goal_created_event,
    create_goal_priority_changed_event,
    create_goal_updated_event,
)
from cognitive_runtime.knowledge.events import (
    create_fact_added_event,
    create_fact_removed_event,
    create_fact_updated_event,
    create_knowledge_queried_event,
)
from cognitive_runtime.rules.events import (
    create_rule_evaluated_event,
    create_rule_matched_event,
    create_rule_registered_event,
    create_rule_removed_event,
)
from cognitive_runtime.working_memory.events import (
    create_wm_activated_event,
    create_wm_cleared_event,
    create_wm_deactivated_event,
    create_wm_evicted_event,
)


def run_event_integrity_test():
    print("Starting Event Integrity Test...")
    
    events = []
    try:
        # Core
        events.append(create_runtime_started_event())
        events.append(create_runtime_stopping_event())
        events.append(create_runtime_stopped_event())
        
        # Goals
        events.append(create_goal_created_event("goal_1"))
        events.append(create_goal_updated_event("goal_1"))
        events.append(create_goal_completed_event("goal_1"))
        events.append(create_goal_cancelled_event("goal_1"))
        events.append(create_goal_priority_changed_event("goal_1", 5))
        
        # Working Memory
        events.append(create_wm_activated_event("item_1"))
        events.append(create_wm_deactivated_event("item_1"))
        events.append(create_wm_evicted_event("item_1"))
        events.append(create_wm_cleared_event())
        
        # Knowledge
        events.append(create_fact_added_event("fact_1", "test"))
        events.append(create_fact_removed_event("fact_1", "test"))
        events.append(create_fact_updated_event("fact_1", "test"))
        events.append(create_knowledge_queried_event({"q":"a"}, 1, "test"))
        
        # Decisions
        events.append(create_decision_created_event("dec_1", {"action": "test"}))
        events.append(create_decision_explained_event("dec_1", "explain"))
        events.append(create_decision_rejected_event("dec_1", "reject"))
        
        # Rules
        events.append(create_rule_registered_event("rule_1", "test"))
        events.append(create_rule_removed_event("rule_1", "test"))
        events.append(create_rule_evaluated_event(1, 1, ["rule_1"], "test"))
        events.append(create_rule_matched_event("rule_1", {"c": "b"}, "test"))
        
    except Exception as e:
        print(f"EVENT INTEGRITY TEST FAILED: {e}")
        sys.exit(1)
        
    # Validate Pydantic model dump
    for event in events:
        d = event.model_dump()
        if "event_type" not in d or "event_id" not in d:
            print(f"EVENT INTEGRITY TEST FAILED: Missing base fields in {event}")
            sys.exit(1)
            
    print(f"EVENT INTEGRITY TEST PASSED: {len(events)} events validated.")

if __name__ == "__main__":
    run_event_integrity_test()
