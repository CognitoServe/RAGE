"""
DefaultExecutor — RFC-0013

The concrete V1 implementation of the Executor.

Orchestration Flow
------------------
Every execution follows this exact sequence. No step is skipped; no step
contains OS interaction:

    1. Pre-validate   — Is the executor running? Is the action in RUNNING state?
                        Is this action_id already being dispatched?
    2. Resolve        — Look up the ActionAdapter for this ActionType.
    3. Guard          — Add action_id to _executing (duplicate guard).
    4. Announce       — Publish ActionExecutionStarted.
    5. Dispatch       — Call adapter.execute(action). Record wall-clock time.
    6. Record         — Update internal stats counters.
    7. Release guard  — Remove action_id from _executing.
    8. Publish        — ActionExecutionCompleted or ActionExecutionFailed.
    9. Return         — ExecutionResult to caller.

execute_next() wraps this sequence with queue interaction:
    Before step 1: queue.dequeue() (gets a RUNNING action)
    After step 9:  queue.complete() or queue.fail()

Thread Safety
-------------
A single RLock guards all mutable state: _running, _executing, _adapters,
and the stats counters. The adapter call itself (step 5) happens OUTSIDE the
lock to avoid holding it across potentially slow or blocking operations.
The _executing set is updated inside the lock (steps 3 and 7) using a
try/finally to guarantee release even if the adapter raises.

Stats Accounting
----------------
_total_executed is incremented unconditionally on every dispatch attempt
that reaches the adapter call (steps 5+). _success_count and _failure_count
are mutually exclusive. _total_time_ms accumulates wall-clock time for
averaging. None of these ever decrease.

Adapter Failure Handling
------------------------
If adapter.execute() raises any exception:
  - The exception is caught here.
  - An ExecutionResult(success=False) is constructed from it.
  - execute_next() sees success=False and calls queue.fail().
  - An ActionExecutionFailed event is published.
  - The exception is NOT re-raised to the caller of execute().
  This ensures callers always get a structured ExecutionResult, never an
  unexpected exception from adapter internals.
"""

import threading
import time

import structlog

from cognitive_runtime.actions.models import Action, ActionStatus, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.queue.interfaces import ExecutionQueue

from .events import (
    create_action_execution_completed_event,
    create_action_execution_failed_event,
    create_action_execution_started_event,
    create_adapter_resolution_failed_event,
    create_executor_started_event,
    create_executor_stopped_event,
    create_unsupported_action_type_event,
)
from .exceptions import (
    AdapterNotFoundError,
    DuplicateExecutionError,
    ExecutorNotRunningError,
    InvalidActionStateError,
)
from .interfaces import ActionAdapter, Executor
from .models import ExecutionResult, ExecutorStats

logger = structlog.get_logger(__name__)


class DefaultExecutor(Executor):
    """
    Single-worker, synchronous executor.

    V1 design: no background threads, no parallelism. The caller drives
    execution by calling execute_next() in a loop. This makes the executor
    trivially testable and allows future WorkerThread wrappers to provide
    async/parallel behavior without modifying this class.
    """

    def __init__(self, queue: ExecutionQueue, event_bus: EventBus) -> None:
        self._queue = queue
        self._bus = event_bus
        self._lock = threading.RLock()

        # Adapter registry: ActionType → ActionAdapter
        self._adapters: dict[ActionType, ActionAdapter] = {}

        # Lifecycle state
        self._running: bool = False

        # Duplicate-dispatch guard: set of action_ids currently in flight
        self._executing: set[str] = set()

        # Observability counters (mutated under lock)
        self._current_action_id: str | None = None
        self._total_executed: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._total_time_ms: float = 0.0
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the executor as running."""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._bus.publish(create_executor_started_event())
        logger.info("executor_started")

    def stop(self) -> None:
        """Mark the executor as stopped."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._bus.publish(create_executor_stopped_event())
        logger.info("executor_stopped")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    # ------------------------------------------------------------------
    # Adapter registry
    # ------------------------------------------------------------------

    def register_adapter(self, action_type: ActionType, adapter: ActionAdapter) -> None:
        """Register an adapter for an ActionType. Replaces any existing registration."""
        with self._lock:
            self._adapters[action_type] = adapter
        logger.info("adapter_registered", action_type=action_type)

    def _resolve_adapter(self, action: Action) -> ActionAdapter:
        """
        Resolve the adapter for the given Action's type.

        Must be called under lock or with awareness that the registry could
        change between check and use. In V1 (single worker), this is safe.

        Raises
        ------
        AdapterNotFoundError
            If no adapter is registered for the action's type.
        """
        with self._lock:
            adapter = self._adapters.get(action.type)

        if adapter is None:
            self._bus.publish(
                create_adapter_resolution_failed_event(action.action_id, action.type)
            )
            raise AdapterNotFoundError(
                f"No adapter registered for ActionType '{action.type}'. "
                f"action_id={action.action_id}"
            )

        if not adapter.supports(action.type):
            self._bus.publish(
                create_unsupported_action_type_event(action.action_id, action.type)
            )
            raise AdapterNotFoundError(
                f"Adapter registered for '{action.type}' does not support it. "
                f"action_id={action.action_id}"
            )

        return adapter

    # ------------------------------------------------------------------
    # Core dispatch kernel
    # ------------------------------------------------------------------

    def execute(self, action: Action) -> ExecutionResult:
        """
        Directly dispatch a RUNNING Action through its adapter.

        This is the inner kernel of the executor. It does NOT interact with
        the Queue. execute_next() wraps this with queue interaction.
        """
        # --- Pre-validation (under lock) ---
        with self._lock:
            if not self._running:
                raise ExecutorNotRunningError(
                    "Executor has not been started. Call start() first."
                )

            if action.status != ActionStatus.RUNNING:
                raise InvalidActionStateError(
                    f"Action {action.action_id} is in state '{action.status}', "
                    f"expected RUNNING. Only RUNNING actions can be dispatched."
                )

            if action.action_id in self._executing:
                raise DuplicateExecutionError(
                    f"Action {action.action_id} is already being dispatched by this executor."
                )

            # Claim the slot
            self._executing.add(action.action_id)
            self._current_action_id = action.action_id

        # --- Adapter resolution (outside lock, may publish events) ---
        try:
            adapter = self._resolve_adapter(action)
        except AdapterNotFoundError as exc:
            with self._lock:
                self._executing.discard(action.action_id)
                self._current_action_id = None
                self._failure_count += 1
                self._total_executed += 1
                self._last_error = str(exc)
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=False,
                error=str(exc),
                duration_ms=0.0,
            )

        # --- Dispatch (outside lock — adapter may be slow/blocking) ---
        self._bus.publish(
            create_action_execution_started_event(action.action_id, action.type)
        )

        started_at_ns = time.monotonic_ns()
        result: ExecutionResult

        try:
            result = adapter.execute(action)

        except Exception as exc:
            duration_ms = (time.monotonic_ns() - started_at_ns) / 1_000_000
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "adapter_execute_raised",
                action_id=action.action_id,
                action_type=action.type,
                error=error_msg,
                exc_info=True,
            )
            result = ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )

        else:
            duration_ms = (time.monotonic_ns() - started_at_ns) / 1_000_000
            # Ensure duration is reflected correctly even if adapter filled it
            if result.duration_ms == 0.0:
                result = result.model_copy(update={"duration_ms": duration_ms})

        # --- Update stats (under lock) ---
        with self._lock:
            self._executing.discard(action.action_id)
            self._current_action_id = None
            self._total_executed += 1
            self._total_time_ms += result.duration_ms
            if result.success:
                self._success_count += 1
            else:
                self._failure_count += 1
                self._last_error = result.error

        # --- Publish outcome event ---
        if result.success:
            self._bus.publish(
                create_action_execution_completed_event(
                    action.action_id, action.type, result.duration_ms
                )
            )
        else:
            self._bus.publish(
                create_action_execution_failed_event(
                    action.action_id, action.type, result.error or "unknown", result.duration_ms
                )
            )

        return result

    # ------------------------------------------------------------------
    # Queue-driven dispatch
    # ------------------------------------------------------------------

    def execute_next(self) -> ExecutionResult | None:
        """
        Dequeue the next pending Action and dispatch it.

        Returns None if the queue is empty.
        """
        with self._lock:
            if not self._running:
                raise ExecutorNotRunningError(
                    "Executor has not been started. Call start() first."
                )

        action = self._queue.dequeue()
        if action is None:
            return None

        result = self.execute(action)

        # Notify queue of outcome
        if result.success:
            try:
                self._queue.complete(action.action_id)
            except Exception as exc:
                logger.error(
                    "queue_complete_failed",
                    action_id=action.action_id,
                    error=str(exc),
                    exc_info=True,
                )
        else:
            try:
                self._queue.fail(action.action_id, result.error or "unknown")
            except Exception as exc:
                logger.error(
                    "queue_fail_failed",
                    action_id=action.action_id,
                    error=str(exc),
                    exc_info=True,
                )

        return result

    # ------------------------------------------------------------------
    # Queue delegation
    # ------------------------------------------------------------------

    def submit(self, action: Action) -> None:
        """Enqueue an Action for later execution. Does not execute."""
        self._queue.enqueue(action)

    def cancel(self, action_id: str) -> bool:
        """Cancel a pending or running Action via the Queue."""
        return self._queue.cancel(action_id)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def stats(self) -> ExecutorStats:
        """Return a point-in-time snapshot of executor metrics."""
        with self._lock:
            avg = (
                self._total_time_ms / self._total_executed
                if self._total_executed > 0
                else 0.0
            )
            return ExecutorStats(
                is_running=self._running,
                current_action_id=self._current_action_id,
                total_executed=self._total_executed,
                success_count=self._success_count,
                failure_count=self._failure_count,
                average_execution_time_ms=avg,
                last_error=self._last_error,
            )
