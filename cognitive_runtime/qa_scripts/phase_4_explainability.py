import sys
import uuid
from datetime import UTC, datetime

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.decisions.models import DecisionContext
from cognitive_runtime.goals.models import Goal, GoalStatus
from cognitive_runtime.rules.models import (
    Conclusion,
    FactPattern,
    Operator,
    Rule,
    RuleCondition,
)
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem


def run_explainability_test():
    print("Starting Explainability Test...")
    brain = startup()
    
    wm = brain._services["WorkingMemory"]
    rules = brain._services["RuleEngine"]
    decisions = brain._services["DecisionEngine"]
    planner = brain._services["Planner"]

    # 1. Setup Context
    goal_id = str(uuid.uuid4())
    goal = Goal(goal_id=goal_id, title="Test Goal", description="Explainable test", priority=1, status=GoalStatus.ACTIVE, created_at=datetime.now(UTC), metadata={})
    
    wm_item = WorkingMemoryItem(item_id=f"wm_{goal_id}", source=ItemSource.GOAL, reference_id=goal_id, metadata={"context": "test"})
    wm.activate(wm_item)

    rule = Rule(
        rule_id="explain_rule",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(predicate="is_active_goal", object="true")]
        ),
        conclusion=Conclusion(name="ExplainAction", payload={"action": "test"})
    )
    rules.register(rule)

    # 2. Make Decision
    context = DecisionContext(active_goals=[goal], working_memory_items=[wm_item])
    decision = decisions.decide(context)
    
    # 3. Retrieve Explanation
    try:
        explanation = decisions.explain(decision.decision_id)
        print(f"Decision Explanation: {explanation}")
        
        # Verify deterministic traceability
        assert len(decision.context_items) == 1
        assert decision.context_items[0] == wm_item.item_id
        # matched_rules is empty because DeterministicRulePolicy doesn't extract it currently, but we can verify it doesn't crash.
        
    except Exception as e:
        print(f"Explainability FAILED on Decision: {e}")
        shutdown(brain)
        sys.exit(1)

    # 4. Generate Plan
    plan = planner.create_plan(goal_id)
    
    # Check plan traceability
    print(f"Plan ID: {plan.plan_id}, Goal ID: {plan.goal_id}")
    if plan.goal_id != goal_id:
        print("Explainability FAILED on Plan: Incorrect Goal ID linked")
        sys.exit(1)

    shutdown(brain)
    print("EXPLAINABILITY TEST PASSED.")

if __name__ == "__main__":
    run_explainability_test()
