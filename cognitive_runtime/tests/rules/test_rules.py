import threading

import pytest

from cognitive_runtime.events.bus import SynchronousEventBus
from cognitive_runtime.knowledge.models import Fact
from cognitive_runtime.rules.engine import ForwardChainingRuleEngine
from cognitive_runtime.rules.exceptions import DuplicateRuleError, RuleValidationError
from cognitive_runtime.rules.models import (
    Conclusion,
    FactPattern,
    Operator,
    Rule,
    RuleCondition,
)


def test_single_rule_match():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="User", predicate="is_a", object="Person")]
        ),
        conclusion=Conclusion(name="AccessGranted", payload={"status": "granted"})
    )
    
    engine.register(rule)
    
    facts = [
        Fact(subject="User", predicate="is_a", object="Person", source="system")
    ]
    
    conclusions = engine.evaluate(facts)
    
    assert len(conclusions) == 1
    assert conclusions[0].name == "AccessGranted"
    assert conclusions[0].payload == {"status": "granted"}

def test_multiple_rules_priority_sorting():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule1 = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A", predicate="is", object="B")]
        ),
        conclusion=Conclusion(name="Action1"),
        priority=10
    )
    
    rule2 = Rule(
        rule_id="rule_2",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A", predicate="is", object="B")]
        ),
        conclusion=Conclusion(name="Action2"),
        priority=20
    )
    
    engine.register(rule1)
    engine.register(rule2)
    
    facts = [Fact(subject="A", predicate="is", object="B", source="system")]
    conclusions = engine.evaluate(facts)
    
    assert len(conclusions) == 2
    # Rule 2 has higher priority, so it should be evaluated and match first
    assert conclusions[0].name == "Action2"
    assert conclusions[1].name == "Action1"

def test_and_operator_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[
                FactPattern(subject="A", predicate="is", object="B"),
                FactPattern(subject="C", predicate="is", object="D")
            ]
        ),
        conclusion=Conclusion(name="Match")
    )
    engine.register(rule)
    
    # Missing second fact
    facts = [Fact(subject="A", predicate="is", object="B", source="system")]
    assert len(engine.evaluate(facts)) == 0
    
    # Has both facts
    facts.append(Fact(subject="C", predicate="is", object="D", source="system"))
    assert len(engine.evaluate(facts)) == 1

def test_or_operator_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.OR,
            patterns=[
                FactPattern(subject="A", predicate="is", object="B"),
                FactPattern(subject="C", predicate="is", object="D")
            ]
        ),
        conclusion=Conclusion(name="Match")
    )
    engine.register(rule)
    
    facts = [Fact(subject="A", predicate="is", object="B", source="system")]
    assert len(engine.evaluate(facts)) == 1
    
    facts = [Fact(subject="C", predicate="is", object="D", source="system")]
    assert len(engine.evaluate(facts)) == 1
    
    facts = [Fact(subject="X", predicate="is", object="Y", source="system")]
    assert len(engine.evaluate(facts)) == 0

def test_not_operator_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.NOT,
            patterns=[
                FactPattern(subject="Enemy", predicate="is", object="Present")
            ]
        ),
        conclusion=Conclusion(name="Safe")
    )
    engine.register(rule)
    
    # No enemy present -> safe
    facts = [Fact(subject="Friend", predicate="is", object="Present", source="system")]
    assert len(engine.evaluate(facts)) == 1
    
    # Enemy present -> not safe
    facts.append(Fact(subject="Enemy", predicate="is", object="Present", source="system"))
    assert len(engine.evaluate(facts)) == 0

def test_invalid_rules():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[]
        ),
        conclusion=Conclusion(name="Action")
    )
    
    # Sub-conditions should be empty if patterns is empty, but this has NO conditions to check
    with pytest.raises(RuleValidationError):
        engine.register(rule)

def test_duplicate_rules():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A", predicate="is", object="B")]
        ),
        conclusion=Conclusion(name="Action")
    )
    engine.register(rule)
    
    with pytest.raises(DuplicateRuleError):
        engine.register(rule)

def test_event_publication():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    events = []
    def on_event(event):
        events.append(event)
        
    bus.subscribe("RuleRegistered", on_event)
    bus.subscribe("RuleRemoved", on_event)
    bus.subscribe("RuleEvaluated", on_event)
    bus.subscribe("RuleMatched", on_event)
    
    rule = Rule(
        rule_id="rule_1",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A", predicate="is", object="B")]
        ),
        conclusion=Conclusion(name="Action")
    )
    engine.register(rule)
    
    assert len(events) == 1
    assert events[0].event_type == "RuleRegistered"
    assert events[0].payload["rule_id"] == "rule_1"
    
    facts = [Fact(subject="A", predicate="is", object="B", source="system")]
    engine.evaluate(facts)
    
    # Should publish RuleMatched then RuleEvaluated
    assert len(events) == 3
    assert events[1].event_type == "RuleMatched"
    assert events[1].payload["rule_id"] == "rule_1"
    assert events[2].event_type == "RuleEvaluated"
    assert events[2].payload["matched_rules"] == ["rule_1"]
    
    engine.remove("rule_1")
    assert len(events) == 4
    assert events[3].event_type == "RuleRemoved"
    assert events[3].payload["rule_id"] == "rule_1"

def test_thread_safety():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    def register_rules(start_id: int, count: int):
        for i in range(count):
            rule = Rule(
                rule_id=f"rule_{start_id + i}",
                condition=RuleCondition(
                    operator=Operator.AND,
                    patterns=[FactPattern(subject="A", predicate="is", object="B")]
                ),
                conclusion=Conclusion(name="Action")
            )
            engine.register(rule)
            
    threads = []
    for i in range(5):
        t = threading.Thread(target=register_rules, args=(i*100, 100))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    rules = engine.list_rules()
    assert len(rules) == 500


def test_invalid_subcondition_validation():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_invalid_sub",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A")],
            sub_conditions=[
                RuleCondition(
                    operator=Operator.AND,
                    patterns=[]  # Empty patterns -> invalid
                )
            ]
        ),
        conclusion=Conclusion(name="Action")
    )
    with pytest.raises(RuleValidationError):
        engine.register(rule)

def test_and_subcondition_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_and_sub",
        condition=RuleCondition(
            operator=Operator.AND,
            patterns=[FactPattern(subject="A")],
            sub_conditions=[
                RuleCondition(
                    operator=Operator.AND,
                    patterns=[FactPattern(subject="B")]
                )
            ]
        ),
        conclusion=Conclusion(name="Action")
    )
    engine.register(rule)
    
    # Missing sub-condition fact -> evaluates to False
    facts = [Fact(subject="A", predicate="is", object="B", source="system")]
    assert len(engine.evaluate(facts)) == 0

    # Has both -> True
    facts.append(Fact(subject="B", predicate="is", object="C", source="system"))
    assert len(engine.evaluate(facts)) == 1

def test_or_subcondition_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_or_sub",
        condition=RuleCondition(
            operator=Operator.OR,
            patterns=[FactPattern(subject="A")],
            sub_conditions=[
                RuleCondition(
                    operator=Operator.AND,
                    patterns=[FactPattern(subject="B")]
                )
            ]
        ),
        conclusion=Conclusion(name="Action")
    )
    engine.register(rule)
    
    # Sub-condition is true -> evaluates to True
    facts = [Fact(subject="B", predicate="is", object="C", source="system")]
    assert len(engine.evaluate(facts)) == 1

def test_not_subcondition_logic():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    
    rule = Rule(
        rule_id="rule_not_sub",
        condition=RuleCondition(
            operator=Operator.NOT,
            patterns=[FactPattern(subject="A")],
            sub_conditions=[
                RuleCondition(
                    operator=Operator.AND,
                    patterns=[FactPattern(subject="B")]
                )
            ]
        ),
        conclusion=Conclusion(name="Action")
    )
    engine.register(rule)
def test_empty_or_condition_eval():
    bus = SynchronousEventBus()
    engine = ForwardChainingRuleEngine(bus)
    # Directly test the unreachable branch
    cond = RuleCondition(operator=Operator.OR, patterns=[], sub_conditions=[])
    assert not engine._evaluate_condition(cond, [])
