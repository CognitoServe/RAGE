import threading
from datetime import UTC, datetime

from cognitive_runtime.events.interfaces import EventBus

from .events import (
    create_goal_cancelled_event,
    create_goal_completed_event,
    create_goal_created_event,
    create_goal_priority_changed_event,
    create_goal_updated_event,
)
from .exceptions import (
    DuplicateGoalError,
    GoalNotFoundError,
    InvalidStateTransitionError,
)
from .interfaces import GoalManager
from .models import Goal, GoalStatus


class InMemoryGoalManager(GoalManager):
    """
    Thread-safe in-memory state tracker for goals.
    """

    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._goals: dict[str, Goal] = {}
        self._lock = threading.RLock()

        self._terminal_states = {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
        }

    def _validate_transition(self, current: GoalStatus, target: GoalStatus) -> None:
        """Validate if a state transition is legal."""
        if current in self._terminal_states and target not in self._terminal_states:
            # Cannot transition from terminal back to active
            raise InvalidStateTransitionError(
                f"Cannot transition from terminal state {current} to {target}"
            )

    def create(self, goal: Goal) -> None:
        with self._lock:
            if goal.goal_id in self._goals:
                raise DuplicateGoalError(f"Goal with ID {goal.goal_id} already exists")

            # Defensive copy
            self._goals[goal.goal_id] = goal.model_copy(deep=True)

        self._bus.publish(create_goal_created_event(goal.goal_id))

    def update(self, goal: Goal) -> None:
        with self._lock:
            if goal.goal_id not in self._goals:
                raise GoalNotFoundError(f"Goal with ID {goal.goal_id} not found")

            current_goal = self._goals[goal.goal_id]
            self._validate_transition(current_goal.status, goal.status)

            priority_changed = current_goal.priority != goal.priority
            new_priority = goal.priority

            # Apply update
            # We enforce that created_at is immutable, updated_at is refreshed
            updated = goal.model_copy(
                update={
                    "created_at": current_goal.created_at,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._goals[goal.goal_id] = updated

        self._bus.publish(create_goal_updated_event(goal.goal_id))

        if priority_changed:
            self._bus.publish(
                create_goal_priority_changed_event(goal.goal_id, new_priority)
            )

    def _set_status(self, goal_id: str, status: GoalStatus) -> None:
        with self._lock:
            if goal_id not in self._goals:
                raise GoalNotFoundError(f"Goal with ID {goal_id} not found")

            current = self._goals[goal_id]
            self._validate_transition(current.status, status)

            updated = current.model_copy(
                update={"status": status, "updated_at": datetime.now(UTC)}
            )
            self._goals[goal_id] = updated

    def complete(self, goal_id: str) -> None:
        self._set_status(goal_id, GoalStatus.COMPLETED)
        self._bus.publish(create_goal_completed_event(goal_id))

    def cancel(self, goal_id: str) -> None:
        self._set_status(goal_id, GoalStatus.CANCELLED)
        self._bus.publish(create_goal_cancelled_event(goal_id))

    def list(self) -> list[Goal]:
        with self._lock:
            return [g.model_copy(deep=True) for g in self._goals.values()]

    def highest_priority(self) -> Goal | None:
        with self._lock:
            active_goals = [
                g for g in self._goals.values() if g.status not in self._terminal_states
            ]
            if not active_goals:
                return None

            # Sort descending by priority, tie-break by oldest created_at
            highest = max(
                active_goals, key=lambda g: (g.priority, -g.created_at.timestamp())
            )
            return highest.model_copy(deep=True)
