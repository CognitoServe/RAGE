from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ItemSource(StrEnum):
    MEMORY = "MEMORY"
    KNOWLEDGE = "KNOWLEDGE"
    GOAL = "GOAL"
    RULE = "RULE"
    FUTURE = "FUTURE"
    INTERNAL = "INTERNAL"  # Fallback/generic


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkingMemoryItem(BaseModel):
    item_id: str
    source: ItemSource
    reference_id: str
    activation_score: float = 1.0
    inserted_at: datetime = Field(default_factory=utc_now)
    last_accessed: datetime = Field(default_factory=utc_now)
    ttl: int | None = None  # Time to live in seconds
    metadata: dict[str, Any] = Field(default_factory=dict)
