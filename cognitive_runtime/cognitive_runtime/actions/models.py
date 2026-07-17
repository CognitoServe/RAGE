"""
Action Model — RFC-0011

Design Rationale
----------------

**Why Action is separate from Planner:**
The Planner operates at the level of *intent* — it produces Steps that describe
what needs to be accomplished in abstract terms. An Action translates that intent
into a concrete, typed, executable descriptor that can be safely transported to
any execution layer without requiring knowledge of planning algorithms or goal
state. This separation allows the Planner to be retrained or replaced without
touching the execution contract, and allows executors to be built independently.

**Why Action is immutable:**
Actions are transport primitives. Once an Action is created, every module that
receives it must see exactly the same data. If a module could mutate an Action
mid-flight (e.g., changing its `target` or `parameters`), execution would become
non-deterministic and audit logs would become unreliable. Pydantic's
`frozen=True` enforces this at the language level — any attempt to set a field
raises a `ValidationError`, making the constraint impossible to accidentally
violate.

**Why Action never performs execution:**
An Action is pure data. Mixing execution logic into a data model violates the
Single Responsibility Principle, ties the data structure to a specific runtime
environment, and prevents the Action from being serialized or transported across
module boundaries. All execution belongs in a future `Executor` module that
*receives* Actions and acts upon them.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ActionType(StrEnum):
    """
    The category of operation an Action represents.

    These types describe the *kind* of work, not how to perform it.
    The executor resolves each type to its concrete implementation.
    """

    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    FILE_MOVE = "FILE_MOVE"
    FILE_COPY = "FILE_COPY"
    FILE_DELETE = "FILE_DELETE"
    DIRECTORY_CREATE = "DIRECTORY_CREATE"
    DIRECTORY_DELETE = "DIRECTORY_DELETE"
    HTTP_GET = "HTTP_GET"
    HTTP_POST = "HTTP_POST"
    PROCESS_START = "PROCESS_START"
    PROCESS_STOP = "PROCESS_STOP"
    PLUGIN_CALL = "PLUGIN_CALL"
    CUSTOM = "CUSTOM"


class ActionStatus(StrEnum):
    """
    The lifecycle state of an Action.

    Valid forward transitions:
        PENDING  → QUEUED
        QUEUED   → RUNNING
        RUNNING  → SUCCESS | FAILED | TIMEOUT
        Any      → CANCELLED  (from non-terminal states)

    Terminal states (no further transitions):
        SUCCESS, FAILED, CANCELLED, TIMEOUT
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


# States from which no further forward transitions are valid.
TERMINAL_ACTION_STATES: frozenset[ActionStatus] = frozenset(
    {ActionStatus.SUCCESS, ActionStatus.FAILED, ActionStatus.CANCELLED, ActionStatus.TIMEOUT}
)

# Valid forward transitions table.
VALID_ACTION_TRANSITIONS: dict[ActionStatus, frozenset[ActionStatus]] = {
    ActionStatus.PENDING: frozenset({ActionStatus.QUEUED, ActionStatus.CANCELLED}),
    ActionStatus.QUEUED: frozenset({ActionStatus.RUNNING, ActionStatus.CANCELLED}),
    ActionStatus.RUNNING: frozenset(
        {ActionStatus.SUCCESS, ActionStatus.FAILED, ActionStatus.TIMEOUT, ActionStatus.CANCELLED}
    ),
    ActionStatus.SUCCESS: frozenset(),
    ActionStatus.FAILED: frozenset(),
    ActionStatus.CANCELLED: frozenset(),
    ActionStatus.TIMEOUT: frozenset(),
}


class ActionResultReference(BaseModel):
    """
    A lightweight pointer to where the result of an Action is stored.

    This is NOT the result itself. The executor writes results to a store and
    records the location here so downstream modules can retrieve them without
    this model needing to hold arbitrary result data.

    Fields
    ------
    action_id : str
        The action whose result this reference describes.
    store : str
        The name of the store (e.g., "working_memory", "file_system", "s3").
    key : str
        The key or path within the store where the result was written.
    metadata : dict
        Optional annotations (e.g., size, content-type, timestamp).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str
    store: str
    key: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    """
    The universal executable instruction used by RAGE.

    An Action is a pure, immutable data descriptor. It represents WHAT should be
    executed but carries no execution logic, no OS awareness, and no reference
    to the planning or goal systems except for correlation IDs.

    Fields
    ------
    action_id : str
        Unique identifier for this action. Auto-generated if not provided.
    plan_id : str
        Correlation ID of the Plan that produced this action.
    step_id : str
        Correlation ID of the Step within the Plan.
    type : ActionType
        The category of operation (e.g., FILE_READ, HTTP_POST).
    target : str
        The primary target of the action (path, URL, process name, plugin ID, etc.).
        Interpretation is type-specific and belongs entirely to the executor.
    parameters : dict
        Additional typed parameters required by the executor.
        Schema is defined by the ActionType and enforced by the executor.
    priority : int
        Execution priority. Higher values = higher priority.
        Default is 0 (normal).
    status : ActionStatus
        Current lifecycle state. Starts at PENDING.
    created_at : datetime
        UTC timestamp of when this action was created.
    scheduled_at : datetime | None
        Optional UTC timestamp for deferred execution.
    started_at : datetime | None
        UTC timestamp set by the executor when execution begins.
    completed_at : datetime | None
        UTC timestamp set by the executor when execution ends.
    metadata : dict
        Arbitrary key-value annotations for observability and debugging.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str = Field(default_factory=_generate_uuid)
    plan_id: str
    step_id: str
    type: ActionType
    target: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0)
    status: ActionStatus = Field(default=ActionStatus.PENDING)
    created_at: datetime = Field(default_factory=_utc_now)
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_terminal(self) -> bool:
        """Return True if this action is in a terminal (non-progressable) state."""
        return self.status in TERMINAL_ACTION_STATES

    def can_transition_to(self, target_status: ActionStatus) -> bool:
        """Return True if transitioning to `target_status` is a valid move."""
        return target_status in VALID_ACTION_TRANSITIONS.get(self.status, frozenset())

    def with_status(self, new_status: ActionStatus) -> "Action":
        """
        Return a new Action with an updated status, preserving all other fields.

        This is the correct way to advance an Action's lifecycle. Because Action
        is frozen, direct assignment is forbidden. The caller is responsible for
        validating the transition before calling this method. Use
        `can_transition_to()` to validate first.

        Args:
            new_status: The target ActionStatus.

        Returns:
            A new Action instance with `status` set to `new_status`.
        """
        return self.model_copy(update={"status": new_status})
