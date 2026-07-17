from abc import ABC, abstractmethod

from .models import Plan, Step


class PlanningStrategy(ABC):
    """
    Strategy for generating steps from a goal.
    Designed for future compatibility with HTN, GOAP, etc.
    """

    @abstractmethod
    def generate_steps(self, goal_id: str, context: dict) -> list[Step]:
        """Generate a list of steps to achieve the goal."""
        pass


class Planner(ABC):
    """
    The Planner converts goals into executable plans.
    It manages the lifecycle of plans but does NOT execute them.
    """

    @abstractmethod
    def create_plan(self, goal_id: str) -> Plan:
        pass

    @abstractmethod
    def next_step(self, plan_id: str) -> Step | None:
        pass

    @abstractmethod
    def current_step(self, plan_id: str) -> Step | None:
        pass

    @abstractmethod
    def mark_complete(self, plan_id: str, step_id: str, success: bool = True) -> None:
        pass

    @abstractmethod
    def cancel_plan(self, plan_id: str) -> None:
        pass

    @abstractmethod
    def plan_status(self, plan_id: str) -> Plan | None:
        pass
