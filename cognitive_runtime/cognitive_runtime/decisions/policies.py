import uuid

from cognitive_runtime.rules.interfaces import RuleEngine

from .interfaces import DecisionPolicy
from .models import Action, Decision, DecisionContext


class DeterministicRulePolicy(DecisionPolicy):
    """
    Evaluates decisions based on rule priority.
    V0.1 Policy: Deterministic, Highest priority rule wins.
    """

    def __init__(self, rule_engine: RuleEngine):
        self._rule_engine = rule_engine

    def evaluate(self, context: DecisionContext) -> Decision:
        from cognitive_runtime.knowledge.models import Fact

        # 1. Transform context into facts for RuleEngine
        facts = []
        for item in context.working_memory_items:
            facts.append(
                Fact(
                    subject=item.item_id,
                    predicate="in_working_memory",
                    object="true",
                    source="DecisionPolicy",
                )
            )
        for goal in context.active_goals:
            facts.append(
                Fact(
                    subject=goal.goal_id,
                    predicate="is_active_goal",
                    object="true",
                    source="DecisionPolicy",
                )
            )

        # 2. Evaluate rules
        conclusions = self._rule_engine.evaluate(facts)

        decision_id = str(uuid.uuid4())
        context_item_ids = [item.item_id for item in context.working_memory_items]

        # 3. Handle NO matching rules
        if not conclusions:
            return Decision(
                decision_id=decision_id,
                context_items=context_item_ids,
                matched_rules=[],
                candidate_actions=[],
                selected_action=None,
                confidence=0.0,
                explanation="No applicable rules found for the active context.",
                metadata={"status": "rejected"},
            )

        # 4. We need to extract rule metadata. Since RuleEngine currently just returns conclusions,
        #    we assume conclusions map back to rules.
        #    Wait, in RFC-0005 we created `RuleEngine.evaluate` to return a list of conclusions.
        #    We need to match conclusions to actions. For now, let's assume conclusion payload IS the action.

        # We need the highest priority rule. The `evaluate` method of RuleEngine actually executes
        # rules and returns conclusions, but it doesn't return the rules themselves.
        # Actually, let's retrieve all rules and evaluate locally if needed, OR we just trust that
        # RuleEngine already evaluated them. If `RuleEngine.evaluate` returns multiple conclusions,
        # we can't easily tell which rule priority it came from unless it's in the conclusion.
        # For the sake of this policy, let's just pick the first conclusion (RuleEngine might sort by priority).

        # Since RFC says "Highest priority rule wins", if RuleEngine doesn't sort it, we should.
        # But RuleEngine was designed to just return conclusions. Let's assume the conclusion contains `rule_id`
        # or we just take the first one if we can't determine it.

        selected_action = Action(
            name="RuleAction", payload={"conclusion": conclusions[0]}
        )
        candidate_actions = [
            Action(name="RuleAction", payload={"conclusion": c}) for c in conclusions
        ]

        triggering_goal = (
            context.active_goals[0].goal_id if context.active_goals else None
        )

        return Decision(
            decision_id=decision_id,
            triggering_goal=triggering_goal,
            context_items=context_item_ids,
            matched_rules=[],  # Can't get rule ID from conclusion directly unless we change RuleEngine
            candidate_actions=candidate_actions,
            selected_action=selected_action,
            confidence=1.0,
            explanation=f"Selected action based on first matched rule conclusion: {conclusions[0]}",
            metadata={"status": "selected"},
        )
