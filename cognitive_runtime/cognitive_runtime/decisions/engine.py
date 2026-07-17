import threading

from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_decision_created_event,
    create_decision_explained_event,
    create_decision_rejected_event,
)
from .exceptions import DecisionNotFoundError
from .interfaces import DecisionEngine, DecisionPolicy
from .models import Decision, DecisionContext


class DefaultDecisionEngine(DecisionEngine):
    def __init__(self, event_bus: EventBus, policy: DecisionPolicy):
        self._bus = event_bus
        self._policy = policy
        self._history: list[Decision] = []
        self._lock = threading.RLock()

    def decide(self, context: DecisionContext) -> Decision:
        with self._lock:
            # Policy evaluation
            decision = self._policy.evaluate(context)
            self._history.append(decision)

            # Event publication
            if decision.selected_action is None:
                event = create_decision_rejected_event(
                    decision.decision_id, decision.explanation
                )
                self._bus.publish(event)
            else:
                event = create_decision_created_event(
                    decision.decision_id,
                    payload={"action": decision.selected_action.model_dump()},
                )
                self._bus.publish(event)

            return decision

    def explain(self, decision_id: str) -> str:
        with self._lock:
            for decision in self._history:
                if decision.decision_id == decision_id:
                    explanation = decision.explanation
                    self._bus.publish(
                        create_decision_explained_event(decision_id, explanation)
                    )
                    return explanation

            raise DecisionNotFoundError(f"Decision {decision_id} not found in history.")

    def last_decision(self) -> Decision | None:
        with self._lock:
            return self._history[-1] if self._history else None

    def decision_history(self, limit: int = 10) -> list[Decision]:
        with self._lock:
            # Return last N elements
            return self._history[-limit:] if limit > 0 else []
