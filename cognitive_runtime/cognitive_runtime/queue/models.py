"""
Queue internal models — RFC-0012

These models are implementation details of the Execution Queue.
They are NOT part of the public API and must not be imported by other modules.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cognitive_runtime.actions.models import Action


class QueueEntry(BaseModel):
    """
    Internal wrapper for an Action inside the pending bucket.

    The `sequence` field is a monotonically increasing integer assigned at
    enqueue time. It is the tiebreaker for FIFO ordering among actions with
    equal priority, and the sort key is always (-priority, sequence).

    This model is frozen: queue entries are never mutated in place.
    When an action's status advances, the old entry is discarded and a new
    Action (produced via `Action.with_status()`) is stored in the appropriate
    bucket.

    Fields
    ------
    action   : The enqueued Action (frozen).
    sequence : Monotonic counter assigned at enqueue time. Determines FIFO order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    sequence: int

    @property
    def sort_key(self) -> tuple[int, int]:
        """Sort key: highest priority first, lowest sequence number first (FIFO)."""
        return (-self.action.priority, self.sequence)


class QueueSnapshot(BaseModel):
    """
    A read-only, point-in-time view of the queue's bucket sizes.

    Used for observability (metrics, health checks, dashboards).
    Never used for control flow.

    Fields
    ------
    pending_count   : Number of actions waiting to be dequeued.
    running_count   : Number of actions currently held as in-flight.
    completed_count : Number of actions marked SUCCESS.
    failed_count    : Number of actions marked FAILED.
    cancelled_count : Number of actions marked CANCELLED.
    total_processed : Sum of completed + failed + cancelled.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_processed(self) -> int:
        return self.completed_count + self.failed_count + self.cancelled_count
