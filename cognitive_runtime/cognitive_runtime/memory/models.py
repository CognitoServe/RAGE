import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def generate_uuid() -> str:
    return str(uuid.uuid4())


def current_utc_timestamp() -> datetime:
    return datetime.now(UTC)


class ExperienceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Experience(BaseModel):
    """Immutable model representing an experience in the RAGE runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_id: str = Field(default_factory=generate_uuid)
    timestamp: datetime = Field(default_factory=current_utc_timestamp)
    source: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: ExperienceStatus = Field(default=ExperienceStatus.ACTIVE)


class SearchQuery(BaseModel):
    """Query model for simple memory searches."""

    memory_id: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
