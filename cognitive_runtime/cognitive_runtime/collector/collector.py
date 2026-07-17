import threading
from typing import Any

from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.models import ExecutionResult
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.memory.models import Experience
from cognitive_runtime.working_memory.interfaces import WorkingMemory
from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem

from .events import (
    create_collector_cleared_event,
    create_execution_recorded_event,
    create_observation_created_event,
    create_result_collected_event,
    create_statistics_updated_event,
)
from .exceptions import CollectorValidationError
from .models import CollectorStatistics, ExecutionObservation


class ResultCollector:
    """
    Receives ExecutionResults, transforms them into cognitive observations,
    and publishes them to Memory and Event subsystems.
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        memory_system: MemorySystem,
    ) -> None:
        self._bus = event_bus
        self._wm = working_memory
        self._ltm = memory_system

        self._lock = threading.RLock()
        self._history: list[ExecutionObservation] = []

        # Running statistics
        self._total = 0
        self._successes = 0
        self._failures = 0
        self._total_duration_ms = 0.0

    def collect(self, result: ExecutionResult) -> None:
        """
        Validates the ExecutionResult, builds an observation,
        and notifies subsystems.
        """
        self._validate(result)

        with self._lock:
            # Create observation
            observation = ExecutionObservation(
                action_id=result.action_id,
                correlation_id=result.metadata.get("correlation_id"),
                plan_id=result.metadata.get("plan_id"),
                success=result.success,
                execution_time=result.duration_ms,
                timestamp=result.completed_at,
                result_summary=result.output
                if result.success
                else (result.error or "Unknown error"),
                metadata=result.metadata,
            )

            # Store history
            self._history.append(observation)

            # Update stats
            self._total += 1
            if observation.success:
                self._successes += 1
            else:
                self._failures += 1
            self._total_duration_ms += observation.execution_time

            stats = self.statistics()

        # Emit standard collector events
        self._bus.publish(
            create_result_collected_event(
                action_id=result.action_id,
                success=result.success,
                duration_ms=result.duration_ms,
            )
        )
        self._bus.publish(
            create_observation_created_event(
                observation_id=observation.observation_id,
                action_id=observation.action_id,
                plan_id=observation.plan_id,
            )
        )

        # Notify Working Memory
        wm_item = WorkingMemoryItem(
            item_id=observation.observation_id,
            source=ItemSource.INTERNAL,
            reference_id=observation.observation_id,
            metadata={
                "type": "ExecutionObservation",
                "action_id": observation.action_id,
            },
        )
        self._wm.activate(wm_item)

        # Notify Long-Term Memory
        exp = Experience(
            memory_id=observation.observation_id,
            source="result_collector",
            category="execution_observation",
            payload={
                "action_id": observation.action_id,
                "plan_id": observation.plan_id,
                "success": observation.success,
                "result": observation.result_summary,
            },
        )
        self._ltm.remember(exp)

        # Emit completion events
        self._bus.publish(create_execution_recorded_event(observation.observation_id))
        self._bus.publish(
            create_statistics_updated_event(
                total=stats.total_executions, success_rate=stats.success_rate
            )
        )

    def _validate(self, result: ExecutionResult) -> None:
        if not result.action_id:
            raise CollectorValidationError("ExecutionResult is missing action_id.")
        if result.completed_at is None:
            raise CollectorValidationError(
                "ExecutionResult is missing completed_at timestamp."
            )

    def history(self) -> list[ExecutionObservation]:
        with self._lock:
            return list(self._history)

    def latest(self) -> ExecutionObservation | None:
        with self._lock:
            return self._history[-1] if self._history else None

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
            self._total = 0
            self._successes = 0
            self._failures = 0
            self._total_duration_ms = 0.0

        self._bus.publish(create_collector_cleared_event())

    def statistics(self) -> CollectorStatistics:
        with self._lock:
            if self._total == 0:
                return CollectorStatistics()

            avg_duration = self._total_duration_ms / self._total
            success_rate = self._successes / self._total
            failure_rate = self._failures / self._total
            last_exec = self._history[-1].timestamp if self._history else None

            return CollectorStatistics(
                total_executions=self._total,
                successful_executions=self._successes,
                failed_executions=self._failures,
                average_duration_ms=avg_duration,
                success_rate=success_rate,
                failure_rate=failure_rate,
                last_execution_time=last_exec,
            )

    def find(self, **kwargs: Any) -> list[ExecutionObservation]:
        """
        Supports finding by action_id, plan_id, or correlation_id.
        """
        action_id = kwargs.get("action_id")
        plan_id = kwargs.get("plan_id")
        correlation_id = kwargs.get("correlation_id")

        with self._lock:
            results = self._history
            if action_id:
                results = [o for o in results if o.action_id == action_id]
            if plan_id:
                results = [o for o in results if o.plan_id == plan_id]
            if correlation_id:
                results = [o for o in results if o.correlation_id == correlation_id]

            return list(results)
