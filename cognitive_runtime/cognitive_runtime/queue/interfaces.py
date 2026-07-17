"""
Execution Queue Interface — RFC-0012

The abstract contract that all queue implementations must satisfy.
Future implementations (distributed, persistent, priority-aging) must conform
to this interface without breaking callers.
"""

from abc import ABC, abstractmethod

from cognitive_runtime.actions.models import Action

from .models import QueueSnapshot


class ExecutionQueue(ABC):
    """
    Abstract contract for the RAGE Execution Queue.

    The queue receives Actions, orders them by scheduling policy, and exposes
    them one at a time to a future Executor. It owns the lifecycle tracking
    (which action is pending, running, completed, failed, cancelled) but never
    executes anything itself.

    Scheduling Policy (V2)
    ----------------------
    - Priority-first: higher `action.priority` values dequeue first.
    - FIFO within equal priority: insertion order is preserved via a monotonic
      sequence counter — no timestamps, no randomness.
    - No parallelism, no DAGs, no dependency graphs in V1.

    Thread Safety
    -------------
    All implementations MUST be thread-safe. The interface makes no guarantee
    about which thread calls which method, so implementations must protect all
    shared state with appropriate locking.

    Executor Callbacks
    ------------------
    `complete()` and `fail()` are the executor's notification points. When an
    executor finishes processing a dequeued Action (successfully or not), it
    calls these methods to signal the outcome. The queue then moves the Action
    to the appropriate terminal bucket and publishes the corresponding event.
    This keeps execution state co-located with the queue without requiring the
    queue to know how execution happens.
    """

    @abstractmethod
    def enqueue(self, action: Action) -> None:
        """
        Accept an Action into the pending bucket.

        The Action's status must be PENDING on arrival. The queue transitions
        it to QUEUED and publishes ActionEnqueued.

        Raises
        ------
        DuplicateActionError
            If an action with the same action_id is already tracked by the queue.
        QueueFullError
            If the queue has reached its capacity limit (future).
        """

    @abstractmethod
    def dequeue(self) -> Action | None:
        """
        Remove and return the highest-priority pending Action.

        Transitions the returned Action to RUNNING and publishes ActionDequeued.
        Returns None if no pending actions exist.
        """

    @abstractmethod
    def peek(self) -> Action | None:
        """
        Return the next Action that would be dequeued, without removing it.

        Non-destructive. Does not change any action's status or publish events.
        Returns None if no pending actions exist.
        """

    @abstractmethod
    def cancel(self, action_id: str) -> bool:
        """
        Cancel a pending or running Action.

        Moves it to CANCELLED, publishes ActionCancelled.
        Returns True if found and cancelled, False if already in a terminal state.

        Raises
        ------
        ActionNotFoundError
            If the action_id is not tracked by the queue at all.
        """

    @abstractmethod
    def retry(self, action_id: str) -> bool:
        """
        Re-enqueue a failed Action.

        Moves it from the failed bucket back to pending with status QUEUED.
        Increments the `retry_attempt` counter in the Action's metadata.
        Returns True if the action was successfully retried.

        Raises
        ------
        ActionNotFoundError
            If the action_id is not in the failed bucket.
        """

    @abstractmethod
    def complete(self, action_id: str) -> None:
        """
        Signal that a running Action completed successfully.

        Called by the executor. Moves the Action from running to completed
        with status SUCCESS. Publishes ActionCompleted.

        Raises
        ------
        ActionNotFoundError
            If the action_id is not currently running.
        """

    @abstractmethod
    def fail(self, action_id: str, reason: str) -> None:
        """
        Signal that a running Action has failed.

        Called by the executor. Moves the Action from running to failed
        with status FAILED. Publishes ActionFailed.

        Raises
        ------
        ActionNotFoundError
            If the action_id is not currently running.
        """

    @abstractmethod
    def contains(self, action_id: str) -> bool:
        """
        Return True if the action_id is tracked in any bucket.

        Does not distinguish between pending, running, completed, etc.
        """

    @abstractmethod
    def size(self) -> int:
        """Return the number of actions in the pending bucket only."""

    @abstractmethod
    def clear(self) -> None:
        """
        Remove all pending Actions. Running, completed, failed, and cancelled
        actions are unaffected.

        Publishes ActionQueueCleared with the count of removed actions.
        """

    @abstractmethod
    def list_pending(self) -> list[Action]:
        """Return a snapshot list of pending Actions in scheduling order."""

    @abstractmethod
    def list_running(self) -> list[Action]:
        """Return a snapshot list of currently running Actions."""

    @abstractmethod
    def list_completed(self) -> list[Action]:
        """Return a snapshot list of successfully completed Actions."""

    @abstractmethod
    def snapshot(self) -> QueueSnapshot:
        """Return a point-in-time read-only view of all bucket sizes."""
