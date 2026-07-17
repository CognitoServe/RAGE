"""
InMemoryExecutionQueue — RFC-0012

The concrete V1 implementation of the Execution Queue.

Design
------
Five internal buckets track every action from arrival to terminal state:

    _pending   : list[QueueEntry]      — sorted by (-priority, sequence)
    _running   : dict[str, Action]     — keyed by action_id
    _completed : list[Action]          — in completion order
    _failed    : dict[str, Action]     — keyed by action_id (retry-eligible)
    _cancelled : list[Action]          — terminal, no further transitions

A single RLock guards all state. Operations that need to publish events do so
*after* releasing relevant critical sections to avoid holding the lock across
potentially slow event handlers.

The queue never modifies Actions in place. Every status advancement is done
via Action.with_status(), which produces a new frozen Action instance. This
preserves the immutability guarantee from RFC-0011.

Monotonic Sequence Counter
--------------------------
`_sequence` is an integer incremented on every enqueue(). It is used as the
FIFO tiebreaker within equal-priority groups. The sort key for the pending
list is `(-priority, sequence)` — simple, deterministic, no clock dependency.

Retry Accounting
----------------
retry() produces a new Action via model_copy() with an incremented
`retry_attempt` key in metadata. The queue treats this as a brand-new entry
(new sequence, same action_id re-checked for duplicates across live buckets).
"""

import threading

from cognitive_runtime.actions.events import (
    create_action_cancelled_event,
    create_action_completed_event,
    create_action_failed_event,
)
from cognitive_runtime.actions.models import Action, ActionStatus
from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_action_dequeued_event,
    create_action_enqueued_event,
    create_action_retried_event,
    create_queue_cleared_event,
)
from .exceptions import ActionNotFoundError, DuplicateActionError
from .interfaces import ExecutionQueue
from .models import QueueEntry, QueueSnapshot


class InMemoryExecutionQueue(ExecutionQueue):
    """
    Thread-safe, priority-first, FIFO-within-priority execution queue.

    This is the V1 implementation. It holds all state in memory and supports
    a single consumer (no parallel dequeue). It is designed for extension:
    the `ExecutionQueue` ABC allows drop-in replacement with a distributed or
    persistent implementation without changing any caller code.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._lock = threading.RLock()
        self._sequence: int = 0

        # Five buckets — never share items between them
        self._pending: list[QueueEntry] = []
        self._running: dict[str, Action] = {}
        self._completed: list[Action] = []
        self._failed: dict[str, Action] = {}
        self._cancelled: list[Action] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_sequence(self) -> int:
        """Return and increment the monotonic sequence counter. Must be called under lock."""
        seq = self._sequence
        self._sequence += 1
        return seq

    def _all_known_ids(self) -> set[str]:
        """Return the set of all tracked action_ids across every bucket. Must be called under lock."""
        ids: set[str] = set()
        ids.update(e.action.action_id for e in self._pending)
        ids.update(self._running.keys())
        ids.update(a.action_id for a in self._completed)
        ids.update(self._failed.keys())
        ids.update(a.action_id for a in self._cancelled)
        return ids

    def _sort_pending(self) -> None:
        """Re-sort the pending list by scheduling key. Must be called under lock."""
        self._pending.sort(key=lambda e: e.sort_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, action: Action) -> None:
        """Accept a PENDING action into the queue."""
        with self._lock:
            if action.action_id in self._all_known_ids():
                raise DuplicateActionError(
                    f"Action {action.action_id} is already tracked by this queue."
                )

            seq = self._next_sequence()
            queued_action = action.with_status(ActionStatus.QUEUED)
            entry = QueueEntry(action=queued_action, sequence=seq)
            self._pending.append(entry)
            self._sort_pending()

        self._bus.publish(
            create_action_enqueued_event(action.action_id, action.priority, seq)
        )

    def dequeue(self) -> Action | None:
        """Remove and return the highest-priority pending action, or None."""
        with self._lock:
            if not self._pending:
                return None

            entry = self._pending.pop(0)
            running_action = entry.action.with_status(ActionStatus.RUNNING)
            self._running[running_action.action_id] = running_action

        self._bus.publish(
            create_action_dequeued_event(running_action.action_id, running_action.priority)
        )
        return running_action

    def peek(self) -> Action | None:
        """Return the next action that would be dequeued, without removing it."""
        with self._lock:
            if not self._pending:
                return None
            # Return a defensive copy of the action (it's already frozen, but be explicit)
            return self._pending[0].action

    def cancel(self, action_id: str) -> bool:
        """Cancel a pending or running action. Returns True if cancelled."""
        with self._lock:
            # Search pending
            for i, entry in enumerate(self._pending):
                if entry.action.action_id == action_id:
                    cancelled = entry.action.with_status(ActionStatus.CANCELLED)
                    self._pending.pop(i)
                    self._cancelled.append(cancelled)
                    break
            else:
                # Search running
                if action_id in self._running:
                    cancelled = self._running.pop(action_id).with_status(
                        ActionStatus.CANCELLED
                    )
                    self._cancelled.append(cancelled)
                else:
                    # Not in any live bucket — check if it exists at all
                    all_ids = self._all_known_ids()
                    if action_id not in all_ids:
                        raise ActionNotFoundError(
                            f"Action {action_id} is not tracked by this queue."
                        )
                    # Already in a terminal bucket — nothing to cancel
                    return False

        self._bus.publish(create_action_cancelled_event(action_id))
        return True

    def retry(self, action_id: str) -> bool:
        """Re-enqueue a failed action with incremented retry counter."""
        with self._lock:
            if action_id not in self._failed:
                raise ActionNotFoundError(
                    f"Action {action_id} is not in the failed bucket."
                )

            failed_action = self._failed.pop(action_id)
            attempt = int(failed_action.metadata.get("retry_attempt", 0)) + 1

            retried_action = failed_action.model_copy(
                update={
                    "status": ActionStatus.QUEUED,
                    "metadata": {**failed_action.metadata, "retry_attempt": attempt},
                }
            )

            seq = self._next_sequence()
            entry = QueueEntry(action=retried_action, sequence=seq)
            self._pending.append(entry)
            self._sort_pending()

        self._bus.publish(create_action_retried_event(action_id, attempt))
        return True

    def complete(self, action_id: str) -> None:
        """Signal that a running action succeeded. Called by the executor."""
        with self._lock:
            if action_id not in self._running:
                raise ActionNotFoundError(
                    f"Action {action_id} is not currently running."
                )
            done = self._running.pop(action_id).with_status(ActionStatus.SUCCESS)
            self._completed.append(done)

        self._bus.publish(create_action_completed_event(action_id))

    def fail(self, action_id: str, reason: str) -> None:
        """Signal that a running action failed. Called by the executor."""
        with self._lock:
            if action_id not in self._running:
                raise ActionNotFoundError(
                    f"Action {action_id} is not currently running."
                )
            failed = self._running.pop(action_id).with_status(ActionStatus.FAILED)
            self._failed[action_id] = failed

        self._bus.publish(create_action_failed_event(action_id, reason))

    def contains(self, action_id: str) -> bool:
        """Return True if the action_id is tracked in any bucket."""
        with self._lock:
            return action_id in self._all_known_ids()

    def size(self) -> int:
        """Return the number of actions in the pending bucket."""
        with self._lock:
            return len(self._pending)

    def clear(self) -> None:
        """Remove all pending actions. Running/completed/failed/cancelled unaffected."""
        with self._lock:
            count = len(self._pending)
            # Move each to cancelled
            for entry in self._pending:
                self._cancelled.append(
                    entry.action.with_status(ActionStatus.CANCELLED)
                )
            self._pending.clear()

        if count > 0:
            self._bus.publish(create_queue_cleared_event(count))

    def list_pending(self) -> list[Action]:
        """Return a snapshot of pending actions in scheduling order."""
        with self._lock:
            return [entry.action for entry in self._pending]

    def list_running(self) -> list[Action]:
        """Return a snapshot of currently running actions."""
        with self._lock:
            return list(self._running.values())

    def list_completed(self) -> list[Action]:
        """Return a snapshot of successfully completed actions."""
        with self._lock:
            return list(self._completed)

    def snapshot(self) -> QueueSnapshot:
        """Return a point-in-time view of all bucket sizes."""
        with self._lock:
            return QueueSnapshot(
                pending_count=len(self._pending),
                running_count=len(self._running),
                completed_count=len(self._completed),
                failed_count=len(self._failed),
                cancelled_count=len(self._cancelled),
            )
