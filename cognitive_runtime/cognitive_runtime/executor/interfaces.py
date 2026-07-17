"""
Executor interfaces — RFC-0013

Abstract contracts that all executor and adapter implementations must satisfy.
Future implementations (parallel workers, remote executors, sandboxed runners)
must conform to these interfaces without breaking callers.
"""

from abc import ABC, abstractmethod

from cognitive_runtime.actions.models import Action, ActionType

from .models import ExecutionResult, ExecutorStats


class ActionAdapter(ABC):
    """
    Abstract contract for an Action execution adapter.

    An ActionAdapter encapsulates all the implementation details for a single
    ActionType. It knows HOW to perform the work (file IO, HTTP, process
    management, plugin calls) — the Executor only knows this interface.

    Every ActionAdapter must be:
    - Stateless or internally thread-safe.
    - Focused on a single ActionType (or a small, cohesive family of types).
    - Free of scheduling, planning, or lifecycle management logic.

    The Executor calls `supports()` during adapter resolution and `execute()`
    during dispatch. Adapters must never call back into the Executor or Queue.
    """

    @abstractmethod
    def execute(self, action: Action) -> ExecutionResult:
        """
        Perform the work described by the given Action.

        The adapter receives a RUNNING action and must return an
        ExecutionResult regardless of outcome. If the operation fails, the
        adapter should return a result with success=False and error set,
        OR raise an exception (the Executor will catch it and produce a
        failure result).

        Args:
            action: The RUNNING action to execute.

        Returns:
            ExecutionResult describing the outcome.
        """

    @abstractmethod
    def supports(self, action_type: ActionType) -> bool:
        """
        Return True if this adapter can handle the given ActionType.

        Used by the Executor during adapter resolution. An adapter may support
        multiple types (e.g., a FileAdapter could support FILE_READ and
        FILE_WRITE), though single-type adapters are preferred for clarity.
        """


class Executor(ABC):
    """
    Abstract contract for the RAGE Executor.

    The Executor is the orchestration bridge between the Execution Queue and
    the ActionAdapter registry. It:
    - Receives Actions from the Queue via execute_next()
    - Validates Action state before dispatch
    - Resolves the correct ActionAdapter
    - Dispatches the Action and collects the result
    - Notifies the Queue of completion or failure
    - Publishes structured lifecycle events

    The Executor NEVER:
    - Performs execution logic (filesystem, HTTP, process, plugins)
    - Accesses goals, memory, knowledge, or planning state
    - Makes scheduling decisions (that is the Queue's responsibility)
    - Spawns background threads in V1 (callers drive execution_next())

    Thread Safety
    -------------
    Implementations must be thread-safe. Multiple callers may invoke
    execute_next() concurrently in future multi-worker configurations.
    The duplicate-execution guard (_executing set) prevents two threads from
    dispatching the same action_id simultaneously.
    """

    @abstractmethod
    def start(self) -> None:
        """
        Mark the executor as running.

        Must be called before execute_next() or execute(). Publishes
        ExecutorStarted. Idempotent — calling start() on an already-running
        executor has no effect.
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Mark the executor as stopped.

        After stop(), execute_next() and execute() raise ExecutorNotRunningError.
        Publishes ExecutorStopped. Idempotent.
        """

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if the executor has been started and not stopped."""

    @abstractmethod
    def execute_next(self) -> ExecutionResult | None:
        """
        Dequeue the next pending Action and dispatch it.

        Pulls one Action from the Queue (highest priority / FIFO), dispatches
        it via execute(), and notifies the Queue of the outcome via
        queue.complete() or queue.fail(). Returns None if the Queue is empty.

        Raises
        ------
        ExecutorNotRunningError
            If the executor has not been started.
        """

    @abstractmethod
    def execute(self, action: Action) -> ExecutionResult:
        """
        Directly dispatch a RUNNING Action.

        This is the core dispatch kernel. It validates the action's state,
        resolves the correct adapter, calls adapter.execute(), records timing,
        and returns an ExecutionResult.

        This method does NOT interact with the Queue. Callers are responsible
        for notifying the queue of the outcome (execute_next() does this
        automatically).

        Args:
            action: Must be in RUNNING status.

        Raises
        ------
        ExecutorNotRunningError
            If the executor has not been started.
        InvalidActionStateError
            If the action is not in RUNNING status.
        DuplicateExecutionError
            If this action_id is already being dispatched.
        AdapterNotFoundError
            If no adapter is registered for the action's type.
        """

    @abstractmethod
    def submit(self, action: Action) -> None:
        """
        Enqueue an Action for later execution.

        Delegates to queue.enqueue(). Does not execute the action.

        Args:
            action: A PENDING action to enqueue.
        """

    @abstractmethod
    def cancel(self, action_id: str) -> bool:
        """
        Cancel a pending or running Action.

        Delegates to queue.cancel(). Returns True if cancelled.
        """

    @abstractmethod
    def register_adapter(self, action_type: ActionType, adapter: ActionAdapter) -> None:
        """
        Register an adapter for a specific ActionType.

        Temporary V1 registry — will be replaced by RFC-0014 (Adapter Registry).
        If an adapter is already registered for this type, it is replaced.

        Args:
            action_type: The ActionType this adapter handles.
            adapter    : The ActionAdapter implementation.
        """

    @abstractmethod
    def stats(self) -> ExecutorStats:
        """Return a point-in-time snapshot of executor health metrics."""
