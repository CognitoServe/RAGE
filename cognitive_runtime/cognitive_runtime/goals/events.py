from cognitive_runtime.events.models import Event


def create_goal_created_event(goal_id: str, source: str = "GoalManager") -> Event:
    return Event(event_type="GoalCreated", payload={"goal_id": goal_id}, source=source)


def create_goal_updated_event(goal_id: str, source: str = "GoalManager") -> Event:
    return Event(event_type="GoalUpdated", payload={"goal_id": goal_id}, source=source)


def create_goal_completed_event(goal_id: str, source: str = "GoalManager") -> Event:
    return Event(
        event_type="GoalCompleted", payload={"goal_id": goal_id}, source=source
    )


def create_goal_cancelled_event(goal_id: str, source: str = "GoalManager") -> Event:
    return Event(
        event_type="GoalCancelled", payload={"goal_id": goal_id}, source=source
    )


def create_goal_priority_changed_event(
    goal_id: str, new_priority: int, source: str = "GoalManager"
) -> Event:
    return Event(
        event_type="GoalPriorityChanged",
        payload={"goal_id": goal_id, "new_priority": new_priority},
        source=source,
    )
