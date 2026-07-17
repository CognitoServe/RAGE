from typing import Any

from cognitive_runtime.events.models import Event


def create_rule_registered_event(rule_id: str, source: str) -> Event:
    return Event(
        event_type="RuleRegistered",
        source=source,
        payload={"rule_id": rule_id},
    )


def create_rule_removed_event(rule_id: str, source: str) -> Event:
    return Event(
        event_type="RuleRemoved",
        source=source,
        payload={"rule_id": rule_id},
    )


def create_rule_evaluated_event(
    fact_count: int, conclusion_count: int, matched_rules: list[str], source: str
) -> Event:
    return Event(
        event_type="RuleEvaluated",
        source=source,
        payload={
            "fact_count": fact_count,
            "conclusion_count": conclusion_count,
            "matched_rules": matched_rules,
        },
    )


def create_rule_matched_event(
    rule_id: str, conclusion: dict[str, Any], source: str
) -> Event:
    return Event(
        event_type="RuleMatched",
        source=source,
        payload={"rule_id": rule_id, "conclusion": conclusion},
    )
