import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def generate_uuid() -> str:
    return str(uuid.uuid4())


def current_utc_timestamp() -> datetime:
    return datetime.now(UTC)


class Event(BaseModel):
    """Base immutable event model for the RAGE cognitive runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=generate_uuid)
    event_type: str
    timestamp: datetime = Field(default_factory=current_utc_timestamp)
    source: str
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
