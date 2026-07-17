
from cognitive_runtime.actions.models import Action, ActionStatus
from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.decisions.interfaces import DecisionEngine
from cognitive_runtime.decisions.models import DecisionContext
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import Executor
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.queue.interfaces import ExecutionQueue


class ExecutionPipeline:
    """
    Orchestrates the top-level execution loop for the cognitive runtime.
    
    Flow:
    GoalManager -> DecisionEngine -> Planner -> ExecutionQueue -> Executor -> ResultCollector
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        goal_manager: GoalManager,
        decision_engine: DecisionEngine,
        planner: Planner,
        execution_queue: ExecutionQueue,
        executor: Executor,
        result_collector: ResultCollector,
    ):
        self._bus = event_bus
        self._goals = goal_manager
        self._decisions = decision_engine
        self._planner = planner
        self._queue = execution_queue
        self._executor = executor
        self._collector = result_collector
        self._goal_plans: dict[str, str] = {}

    def tick(self) -> None:
        """
        Executes one complete cycle of the pipeline.
        This would typically be called in a loop by the main thread.
        """
        # 1. Dispatch any pending actions from the queue
        result = self._executor.execute_next()
        if result:
            self._collector.collect(result)
            # If an action executed, we did some work. We could return here,
            # or continue to process goals. For simplicity, we process everything.

        # 2. Get active goals
        active_goals = self._goals.list()
        
        for goal in active_goals:
            # Check if plan already exists for this goal
            plan = None
            plan_id = self._goal_plans.get(goal.goal_id)
            if plan_id:
                plan = self._planner.plan_status(plan_id)
                
            if not plan:
                # Need to decide to create a plan
                context = DecisionContext(
                    active_goals=[goal],
                    working_memory_items=[]
                )
                decision = self._decisions.decide(context)
                if decision:
                    # In a full system, decision dictates the strategy, here we just ask the planner to create one.
                    plan = self._planner.create_plan(goal.goal_id)
                    self._goal_plans[goal.goal_id] = plan.plan_id
            
            if plan:
                # Push pending steps to ExecutionQueue as Actions
                step = self._planner.next_step(plan.plan_id)
                if step:
                    action = Action(
                        action_id=step.step_id,
                        plan_id=plan.plan_id,
                        step_id=step.step_id,
                        type=step.action_type,
                        target=step.target,
                        parameters=step.parameters,
                        status=ActionStatus.PENDING,
                    )
                    self._queue.enqueue(action)
