from cognitive_runtime.events.models import Event

from .models import Plan


def create_plan_created_event(plan: Plan) -> Event:
    return Event(
        event_type="PlanCreated",
        source="Planner",
        payload={"plan_id": plan.plan_id, "goal_id": plan.goal_id},
    )


def create_plan_updated_event(plan: Plan) -> Event:
    return Event(
        event_type="PlanUpdated",
        source="Planner",
        payload={"plan_id": plan.plan_id, "status": plan.status},
    )


def create_plan_completed_event(plan_id: str) -> Event:
    return Event(
        event_type="PlanCompleted", source="Planner", payload={"plan_id": plan_id}
    )


def create_plan_cancelled_event(plan_id: str) -> Event:
    return Event(
        event_type="PlanCancelled", source="Planner", payload={"plan_id": plan_id}
    )


def create_step_completed_event(plan_id: str, step_id: str) -> Event:
    return Event(
        event_type="StepCompleted",
        source="Planner",
        payload={"plan_id": plan_id, "step_id": step_id},
    )


def create_step_failed_event(plan_id: str, step_id: str) -> Event:
    return Event(
        event_type="StepFailed",
        source="Planner",
        payload={"plan_id": plan_id, "step_id": step_id},
    )
