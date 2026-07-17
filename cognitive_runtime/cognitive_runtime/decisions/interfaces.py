from abc import ABC, abstractmethod

from .models import Decision, DecisionContext


class DecisionPolicy(ABC):
    @abstractmethod
    def evaluate(self, context: DecisionContext) -> Decision:
        """Evaluates context and rules to produce a deterministic decision."""
        pass


class DecisionEngine(ABC):
    @abstractmethod
    def decide(self, context: DecisionContext) -> Decision:
        """Evaluates the current active context and produces a decision."""
        pass

    @abstractmethod
    def explain(self, decision_id: str) -> str:
        """Explains why a decision was selected."""
        pass

    @abstractmethod
    def last_decision(self) -> Decision | None:
        """Returns the most recent decision."""
        pass

    @abstractmethod
    def decision_history(self, limit: int = 10) -> list[Decision]:
        """Returns the history of decisions up to the given limit."""
        pass
