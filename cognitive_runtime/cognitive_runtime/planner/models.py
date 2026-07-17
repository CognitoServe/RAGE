from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cognitive_runtime.actions.models import ActionType


def utc_now() -> datetime:
    return datetime.now(UTC)


class PlanStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Step(BaseModel):
    step_id: str
    order: int
    description: str
    status: StepStatus = StepStatus.PENDING
    action_type: ActionType | str = "UNKNOWN"
    target: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_context: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    plan_id: str
    goal_id: str
    created_at: datetime = Field(default_factory=utc_now)
    status: PlanStatus = PlanStatus.CREATED
    priority: int = 0
    steps: list[Step] = Field(default_factory=list)
