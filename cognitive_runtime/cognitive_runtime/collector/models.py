"""
Models for the Result Collector — RFC-0016
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class ExecutionObservation(BaseModel):
    """
    Immutable representation of an executed action's outcome.

    This is the cognitive observation created by the Result Collector
    from an ExecutionResult.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(default_factory=_generate_uuid)
    correlation_id: str | None = None
    action_id: str
    plan_id: str | None = None
    success: bool
    execution_time: float  # In milliseconds
    timestamp: datetime = Field(default_factory=_utc_now)
    result_summary: dict[str, Any] | str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectorStatistics(BaseModel):
    """
    Read-only snapshot of current Result Collector statistics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_duration_ms: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    last_execution_time: datetime | None = None
