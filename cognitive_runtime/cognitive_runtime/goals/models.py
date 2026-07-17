from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GoalStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Goal(BaseModel):
    goal_id: str
    title: str
    description: str
    priority: int = 0
    status: GoalStatus = GoalStatus.CREATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deadline: datetime | None = None
    parent_goal: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
