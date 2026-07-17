import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def generate_uuid() -> str:
    return str(uuid.uuid4())


def current_utc_timestamp() -> datetime:
    return datetime.now(UTC)


class Fact(BaseModel):
    """Immutable model representing a knowledge fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str = Field(default_factory=generate_uuid)
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str
    created_at: datetime = Field(default_factory=current_utc_timestamp)
    updated_at: datetime = Field(default_factory=current_utc_timestamp)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FactQuery(BaseModel):
    """Query model for finding facts."""

    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    source: str | None = None
    min_confidence: float | None = None
