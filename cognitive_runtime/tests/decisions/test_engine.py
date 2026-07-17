import threading

import pytest

from cognitive_runtime.decisions.engine import DefaultDecisionEngine
from cognitive_runtime.decisions.exceptions import DecisionNotFoundError
from cognitive_runtime.decisions.models import DecisionContext
from cognitive_runtime.decisions.policies import DeterministicRulePolicy
from cognitive_runtime.goals.models import Goal, GoalStatus
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem


class DummyEventBus:
    def __init__(self):
        self.published = []
        
    def publish(self, event):
        self.published.append(event)
        
    def subscribe(self, event_type, handler): pass
    def unsubscribe(self, event_type, handler): pass

class DummyRuleEngine:
    def __init__(self):
        self.mock_conclusions = []
    
    def evaluate(self, facts):
        return self.mock_conclusions

    # Mock interfaces required by policies
    def register(self, rule): pass
    def remove(self, rule_id): pass
    def validate(self, rule): pass
    def list_rules(self): return []

@pytest.fixture
def setup_engine():
    bus = DummyEventBus()
    rule_engine = DummyRuleEngine()
    policy = DeterministicRulePolicy(rule_engine)
    engine = DefaultDecisionEngine(bus, policy)
    return engine, bus, rule_engine

def get_dummy_context():
    return DecisionContext(
        active_goals=[
            Goal(
                goal_id="goal_1",
                title="Test Goal",
                description="Test",
                priority=10,
                status=GoalStatus.ACTIVE
            )
        ],
        working_memory_items=[
            WorkingMemoryItem(
                item_id="wm_1",
                source=ItemSource.MEMORY,
                reference_id="ref_1"
            )
        ]
    )

def test_single_matching_rule(setup_engine):
    engine, bus, rule_engine = setup_engine
    rule_engine.mock_conclusions = ["Action: MoveToTarget"]
    
    context = get_dummy_context()
    decision = engine.decide(context)
    
    assert decision.selected_action is not None
    assert decision.selected_action.name == "RuleAction"
    assert decision.selected_action.payload["conclusion"] == "Action: MoveToTarget"
    
    events = [e for e in bus.published if e.event_type == "DecisionCreated"]
    assert len(events) == 1
    assert events[0].payload["action"]["payload"]["conclusion"] == "Action: MoveToTarget"

def test_multiple_matching_rules(setup_engine):
    engine, bus, rule_engine = setup_engine
    # Policy takes the first one based on our tie breaker implementation
    rule_engine.mock_conclusions = ["Action: HighPriority", "Action: LowPriority"]
    
    context = get_dummy_context()
    decision = engine.decide(context)
    
    assert decision.selected_action is not None
    assert decision.selected_action.payload["conclusion"] == "Action: HighPriority"
    assert len(decision.candidate_actions) == 2

def test_no_matching_rules(setup_engine):
    engine, bus, rule_engine = setup_engine
    rule_engine.mock_conclusions = []
    
    context = get_dummy_context()
    decision = engine.decide(context)
    
    assert decision.selected_action is None
    assert decision.metadata.get("status") == "rejected"
    
    events = [e for e in bus.published if e.event_type == "DecisionRejected"]
    assert len(events) == 1

def test_explain_decision(setup_engine):
    engine, bus, rule_engine = setup_engine
    rule_engine.mock_conclusions = ["Action: Investigate"]
    
    decision = engine.decide(get_dummy_context())
    explanation = engine.explain(decision.decision_id)
    
    assert "Investigate" in explanation
    events = [e for e in bus.published if e.event_type == "DecisionExplained"]
    assert len(events) == 1

def test_explain_not_found(setup_engine):
    engine, _, _ = setup_engine
    with pytest.raises(DecisionNotFoundError):
        engine.explain("nonexistent_id")

def test_history_and_last_decision(setup_engine):
    engine, bus, rule_engine = setup_engine
    
    for i in range(15):
        rule_engine.mock_conclusions = [f"Action: {i}"]
        engine.decide(get_dummy_context())
        
    last = engine.last_decision()
    assert last.selected_action.payload["conclusion"] == "Action: 14"
    
    history = engine.decision_history(limit=5)
    assert len(history) == 5
    assert history[-1].selected_action.payload["conclusion"] == "Action: 14"
    assert history[0].selected_action.payload["conclusion"] == "Action: 10"

def test_thread_safety(setup_engine):
    engine, bus, rule_engine = setup_engine
    rule_engine.mock_conclusions = ["ThreadAction"]
    
    def worker():
        engine.decide(get_dummy_context())
        
    threads = []
    for _ in range(50):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(engine.decision_history(100)) == 50
    assert len(bus.published) == 50
