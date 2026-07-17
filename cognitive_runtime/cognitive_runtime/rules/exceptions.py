class RuleError(Exception):
    """Base class for all Rule Engine exceptions."""

    pass


class DuplicateRuleError(RuleError):
    """Raised when attempting to register a rule that already exists."""

    pass


class RuleValidationError(RuleError):
    """Raised when a rule fails validation."""

    pass
