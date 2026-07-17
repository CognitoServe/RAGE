"""
Executor models — RFC-0013

Data models produced and consumed by the Executor layer.
All models are immutable (frozen=True) — they are records of what happened,
not mutable state holders.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExecutionResult(BaseModel):
    """
    The structured outcome of a single Action dispatch.

    Produced by the Executor after the ActionAdapter returns (or raises).
    This is NOT the raw output of the adapter's work — it is the Executor's
    record of what happened at the orchestration layer.

    Fields
    ------
    action_id    : str
        The action that was dispatched.
    action_type  : str
        The ActionType as a string (for serialisation without circular imports).
    success      : bool
        True if the adapter returned normally; False if it raised.
    output       : dict | None
        Arbitrary adapter output. The Executor passes this through verbatim
        without inspecting or modifying it.
    error        : str | None
        Human-readable failure description when success=False.
    started_at   : datetime
        UTC timestamp immediately before the adapter was called.
    completed_at : datetime
        UTC timestamp immediately after the adapter returned (or raised).
    duration_ms  : float
        Wall-clock execution time in milliseconds.
    metadata     : dict
        Optional annotations (adapter name, retry attempt, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str
    action_type: str
    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime = Field(default_factory=_utc_now)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorStats(BaseModel):
    """
    A point-in-time read-only snapshot of Executor health metrics.

    Used for observability (dashboards, health checks, metrics scraping).
    Never used for control flow.

    Fields
    ------
    is_running              : bool — executor has been started and not stopped.
    current_action_id       : str | None — action_id currently being dispatched, if any.
    total_executed          : int — total dispatches attempted (success + failure).
    success_count           : int — dispatches that returned successfully.
    failure_count           : int — dispatches that raised or were rejected.
    average_execution_time_ms : float — rolling average over all completed dispatches.
    last_error              : str | None — the most recent error message, if any.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_running: bool
    current_action_id: str | None = None
    total_executed: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_execution_time_ms: float = 0.0
    last_error: str | None = None
