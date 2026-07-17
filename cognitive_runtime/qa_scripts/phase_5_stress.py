import sys
import time
from datetime import UTC, datetime

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.decisions.models import DecisionContext
from cognitive_runtime.goals.models import Goal, GoalStatus
from cognitive_runtime.knowledge.models import Fact
from cognitive_runtime.rules.models import (
    Conclusion,
    FactPattern,
    Operator,
    Rule,
    RuleCondition,
)
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem


def run_stress_test(count: int = 1000):
    print(f"Starting Stress Test with {count} iterations...")
    brain = startup()
    
    goal_manager = brain._services["GoalManager"]
    wm = brain._services["WorkingMemory"]
    knowledge = brain._services["KnowledgeSystem"]
    rules = brain._services["RuleEngine"]
    decisions = brain._services["DecisionEngine"]
    
    # 1. Setup a basic rule
    rule = Rule(
        rule_id="stress_rule",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(predicate="is_active_goal", object="true")]
        ),
        conclusion=Conclusion(name="StressAction", payload={"action": "stress"})
    )
    rules.register(rule)

    start_time = time.time()

    try:
        for i in range(count):
            goal_id = f"stress_goal_{i}"
            goal = Goal(goal_id=goal_id, title=f"Goal {i}", description="Stress", priority=1, status=GoalStatus.ACTIVE, created_at=datetime.now(UTC), metadata={})
            goal_manager.create(goal)
            
            # This pushes old ones out if capacity is 20, which is fine, we just want to stress it
            wm_item = WorkingMemoryItem(item_id=f"wm_{goal_id}", source=ItemSource.GOAL, reference_id=goal_id, metadata={})
            wm.activate(wm_item)
            
            knowledge.add_fact(Fact(subject=f"Subj_{i}", predicate="is", object="stress", source="stress"))
            
            # The DecisionPolicy creates a DecisionContext out of current active goals
            # If there are >1000 goals, it might be slow.
            # But the requirement is to run this sequentially. Let's see.
            # We'll just pass the current goal and wm_item.
            context = DecisionContext(active_goals=[goal], working_memory_items=[wm_item])
            decisions.decide(context)
            
            if i % 100 == 0 and i > 0:
                print(f"Processed {i} iterations...")
                
    except Exception as e:
        print(f"STRESS TEST FAILED at iteration {i}: {e}")
        shutdown(brain)
        sys.exit(1)

    duration = time.time() - start_time
    print(f"Completed {count} iterations in {duration:.2f} seconds.")
    
    shutdown(brain)
    print("STRESS TEST PASSED.")

if __name__ == "__main__":
    run_stress_test(1000)
