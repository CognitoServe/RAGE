from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from cognitive_runtime.goals.models import Goal
from cognitive_runtime.working_memory.models import WorkingMemoryItem


def utc_now() -> datetime:
    return datetime.now(UTC)


class Action(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionContext(BaseModel):
    active_goals: list[Goal]
    working_memory_items: list[WorkingMemoryItem]


class Decision(BaseModel):
    decision_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    triggering_goal: str | None = None
    context_items: list[str]  # IDs of WM items
    matched_rules: list[str]  # IDs of rules
    candidate_actions: list[Action]
    selected_action: Action | None
    confidence: float = 1.0
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)
