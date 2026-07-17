from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Operator(StrEnum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class FactPattern(BaseModel):
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None


class RuleCondition(BaseModel):
    operator: Operator = Operator.AND
    patterns: list[FactPattern] = Field(default_factory=list)
    sub_conditions: list["RuleCondition"] = Field(default_factory=list)


class Conclusion(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    condition: RuleCondition
    conclusion: Conclusion
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
