import threading

from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.knowledge.models import Fact

from .events import (
    create_rule_evaluated_event,
    create_rule_matched_event,
    create_rule_registered_event,
    create_rule_removed_event,
)
from .exceptions import DuplicateRuleError, RuleValidationError
from .interfaces import RuleEngine
from .models import Conclusion, FactPattern, Operator, Rule, RuleCondition


class ForwardChainingRuleEngine(RuleEngine):
    """
    A purely functional reasoning component that evaluates facts against rules
    using forward chaining. It only evaluates and returns conclusions without
    modifying state outside its own registered rules.
    """

    def __init__(self, event_bus: EventBus, source_name: str = "RuleEngine"):
        self._event_bus = event_bus
        self._source_name = source_name
        self._rules: dict[str, Rule] = {}
        self._lock = threading.RLock()

    def register(self, rule: Rule) -> None:
        if not self.validate(rule):
            raise RuleValidationError(f"Rule {rule.rule_id} failed validation.")

        with self._lock:
            if rule.rule_id in self._rules:
                raise DuplicateRuleError(f"Rule with ID {rule.rule_id} already exists.")
            self._rules[rule.rule_id] = rule

        event = create_rule_registered_event(rule.rule_id, self._source_name)
        self._event_bus.publish(event)

    def remove(self, rule_id: str) -> None:
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]

        event = create_rule_removed_event(rule_id, self._source_name)
        self._event_bus.publish(event)

    def evaluate(self, facts: list[Fact]) -> list[Conclusion]:
        conclusions = []
        matched_rule_ids = []

        with self._lock:
            # Sort rules by priority descending
            active_rules = [r for r in self._rules.values() if r.enabled]
            active_rules.sort(key=lambda r: r.priority, reverse=True)

        for rule in active_rules:
            if self._evaluate_condition(rule.condition, facts):
                conclusions.append(rule.conclusion)
                matched_rule_ids.append(rule.rule_id)

                # Publish matched event
                event = create_rule_matched_event(
                    rule.rule_id, rule.conclusion.model_dump(), self._source_name
                )
                self._event_bus.publish(event)

        # Publish evaluated event
        event = create_rule_evaluated_event(
            fact_count=len(facts),
            conclusion_count=len(conclusions),
            matched_rules=matched_rule_ids,
            source=self._source_name,
        )
        self._event_bus.publish(event)

        return conclusions

    def validate(self, rule: Rule) -> bool:
        """
        Validates that a rule has a properly structured condition tree.
        At least one pattern or sub-condition must exist at the root,
        unless it's an edge case we wish to explicitly forbid.
        """
        return self._validate_condition(rule.condition)

    def _validate_condition(self, condition: RuleCondition) -> bool:
        if not condition.patterns and not condition.sub_conditions:
            return False
        for sub in condition.sub_conditions:
            if not self._validate_condition(sub):
                return False
        return True

    def list_rules(self) -> list[Rule]:
        with self._lock:
            return list(self._rules.values())

    def _evaluate_condition(self, condition: RuleCondition, facts: list[Fact]) -> bool:
        if condition.operator == Operator.AND:
            # All patterns and sub_conditions must match
            for pattern in condition.patterns:
                if not self._match_pattern(pattern, facts):
                    return False
            for sub in condition.sub_conditions:
                if not self._evaluate_condition(sub, facts):
                    return False
            return True

        elif condition.operator == Operator.OR:
            # At least one pattern or sub_condition must match
            if not condition.patterns and not condition.sub_conditions:
                return False  # Nothing to match

            for pattern in condition.patterns:
                if self._match_pattern(pattern, facts):
                    return True
            for sub in condition.sub_conditions:
                if self._evaluate_condition(sub, facts):
                    return True
            return False

        elif condition.operator == Operator.NOT:
            # None of the patterns or sub_conditions must match
            for pattern in condition.patterns:
                if self._match_pattern(pattern, facts):
                    return False
            for sub in condition.sub_conditions:
                if self._evaluate_condition(sub, facts):
                    return False
            return True

        return False

    def _match_pattern(self, pattern: FactPattern, facts: list[Fact]) -> bool:
        for fact in facts:
            if pattern.subject is not None and fact.subject != pattern.subject:
                continue
            if pattern.predicate is not None and fact.predicate != pattern.predicate:
                continue
            if pattern.object is not None and fact.object != pattern.object:
                continue
            return True
        return False
