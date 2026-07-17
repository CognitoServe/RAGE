import threading
import uuid

from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_plan_cancelled_event,
    create_plan_completed_event,
    create_plan_created_event,
    create_plan_updated_event,
    create_step_completed_event,
    create_step_failed_event,
)
from .exceptions import InvalidPlanStateError, PlanNotFoundError
from .interfaces import Planner, PlanningStrategy
from .models import Plan, PlanStatus, Step, StepStatus


class DefaultPlanner(Planner):
    """
    Default thread-safe implementation of Planner.
    """

    def __init__(self, event_bus: EventBus, strategy: PlanningStrategy):
        self._bus = event_bus
        self._strategy = strategy
        self._plans: dict[str, Plan] = {}
        self._lock = threading.RLock()

    def create_plan(self, goal_id: str) -> Plan:
        with self._lock:
            plan_id = str(uuid.uuid4())
            steps = self._strategy.generate_steps(goal_id, {})

            plan = Plan(
                plan_id=plan_id,
                goal_id=goal_id,
                status=PlanStatus.ACTIVE,  # Assume it starts active
                steps=steps,
            )
            self._plans[plan_id] = plan

            # Deep copy to return
            result = plan.model_copy(deep=True)

        self._bus.publish(create_plan_created_event(result))
        return result

    def next_step(self, plan_id: str) -> Step | None:
        """Returns the first pending step, and marks it as ACTIVE."""
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFoundError(f"Plan {plan_id} not found.")

            plan = self._plans[plan_id]
            if plan.status != PlanStatus.ACTIVE:
                return None

            for i, step in enumerate(plan.steps):
                if step.status == StepStatus.PENDING:
                    # Update status to ACTIVE
                    updated_step = step.model_copy(update={"status": StepStatus.ACTIVE})
                    plan.steps[i] = updated_step
                    return updated_step.model_copy(deep=True)
            return None

    def current_step(self, plan_id: str) -> Step | None:
        """Returns the currently active step without modifying it."""
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFoundError(f"Plan {plan_id} not found.")

            plan = self._plans[plan_id]
            for step in plan.steps:
                if step.status == StepStatus.ACTIVE:
                    return step.model_copy(deep=True)
            return None

    def mark_complete(self, plan_id: str, step_id: str, success: bool = True) -> None:
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFoundError(f"Plan {plan_id} not found.")

            plan = self._plans[plan_id]
            if plan.status != PlanStatus.ACTIVE:
                raise InvalidPlanStateError(f"Plan {plan_id} is not active.")

            step_found = False
            for i, step in enumerate(plan.steps):
                if step.step_id == step_id:
                    step_found = True
                    if not success:
                        plan.steps[i] = step.model_copy(
                            update={"status": StepStatus.FAILED}
                        )
                        self._bus.publish(create_step_failed_event(plan_id, step_id))
                        # If a step fails, the plan fails in V1
                        plan.status = PlanStatus.FAILED
                        self._bus.publish(
                            create_plan_updated_event(plan.model_copy(deep=True))
                        )
                    else:
                        plan.steps[i] = step.model_copy(
                            update={"status": StepStatus.COMPLETED}
                        )
                        self._bus.publish(create_step_completed_event(plan_id, step_id))
                    break

            if not step_found:
                raise ValueError(f"Step {step_id} not found in plan {plan_id}.")

            # Check if plan is fully completed
            if plan.status == PlanStatus.ACTIVE and all(
                s.status == StepStatus.COMPLETED for s in plan.steps
            ):
                plan.status = PlanStatus.COMPLETED
                self._bus.publish(create_plan_completed_event(plan_id))
                self._bus.publish(create_plan_updated_event(plan.model_copy(deep=True)))

    def cancel_plan(self, plan_id: str) -> None:
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFoundError(f"Plan {plan_id} not found.")

            plan = self._plans[plan_id]
            if plan.status in (
                PlanStatus.COMPLETED,
                PlanStatus.FAILED,
                PlanStatus.CANCELLED,
            ):
                return

            plan.status = PlanStatus.CANCELLED
            for i, step in enumerate(plan.steps):
                if step.status in (StepStatus.PENDING, StepStatus.ACTIVE):
                    plan.steps[i] = step.model_copy(
                        update={"status": StepStatus.FAILED}
                    )

        self._bus.publish(create_plan_cancelled_event(plan_id))
        self._bus.publish(
            create_plan_updated_event(self._plans[plan_id].model_copy(deep=True))
        )

    def plan_status(self, plan_id: str) -> Plan | None:
        with self._lock:
            if plan_id not in self._plans:
                return None
            return self._plans[plan_id].model_copy(deep=True)
