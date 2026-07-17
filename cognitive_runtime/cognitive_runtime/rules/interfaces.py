from abc import ABC, abstractmethod

from cognitive_runtime.knowledge.models import Fact

from .models import Conclusion, Rule


class RuleEngine(ABC):
    """Abstract base class defining the contract for a Rule Engine."""

    @abstractmethod
    def register(self, rule: Rule) -> None:
        """Register a new rule.

        Args:
            rule: The rule to register.

        Raises:
            DuplicateRuleError: If a rule with the same ID is already registered.
            RuleValidationError: If the rule is invalid.
        """
        pass

    @abstractmethod
    def remove(self, rule_id: str) -> None:
        """Remove a registered rule.

        Args:
            rule_id: The ID of the rule to remove.
        """
        pass

    @abstractmethod
    def evaluate(self, facts: list[Fact]) -> list[Conclusion]:
        """Evaluate the registered rules against the provided facts.

        Args:
            facts: A list of facts to evaluate.

        Returns:
            A list of conclusions from the matched rules.
        """
        pass

    @abstractmethod
    def validate(self, rule: Rule) -> bool:
        """Validate a rule without registering it.

        Args:
            rule: The rule to validate.

        Returns:
            True if the rule is valid, False otherwise.
        """
        pass

    @abstractmethod
    def list_rules(self) -> list[Rule]:
        """Return a list of all registered rules.

        Returns:
            A list of registered rules.
        """
        pass
