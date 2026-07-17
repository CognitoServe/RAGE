import uuid

from .interfaces import PlanningStrategy
from .models import Step


class SequentialTemplateStrategy(PlanningStrategy):
    """
    V1 Planning Strategy.
    Generates a deterministic sequence of steps based on the goal.
    Does not use search algorithms or dynamic branching.
    """

    def generate_steps(self, goal_id: str, context: dict) -> list[Step]:
        # For V1, we simulate deterministic goal decomposition.
        # In a real system, this might look up templates mapped to goal types.
        # Here we just generate a generic 3-step sequential plan.
        return [
            Step(
                step_id=str(uuid.uuid4()),
                order=1,
                description=f"Initial setup for goal {goal_id}",
                required_context=[],
            ),
            Step(
                step_id=str(uuid.uuid4()),
                order=2,
                description=f"Execute core task for goal {goal_id}",
                required_context=[],
            ),
            Step(
                step_id=str(uuid.uuid4()),
                order=3,
                description=f"Verify completion of goal {goal_id}",
                required_context=[],
            ),
        ]
