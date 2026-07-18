"""
RAGE Runtime API — RFC-0019 Extension

Exposes a read-only HTTP interface into the live cognitive runtime state.
Runs as a background thread. All data originates from real subsystem instances.
"""

import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cognitive_runtime.actions.models import Action
from cognitive_runtime.collector.collector import ResultCollector
from cognitive_runtime.core.models import HealthStatus
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event
from cognitive_runtime.goals.interfaces import GoalManager
from cognitive_runtime.memory.interfaces import MemorySystem
from cognitive_runtime.memory.models import SearchQuery
from cognitive_runtime.planner.interfaces import Planner
from cognitive_runtime.queue.interfaces import ExecutionQueue
from cognitive_runtime.working_memory.interfaces import WorkingMemory


# ---------------------------------------------------------------------------
# Module-level runtime context — populated by lifecycle.py after startup
# ---------------------------------------------------------------------------

class _RuntimeContext:
    """
    Holds live references to all runtime subsystems.
    Populated once after BrainCore.start() completes.
    Never mutated by the API layer — read-only from here.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health_fn: Callable[[], HealthStatus] | None = None
        self._goal_manager: GoalManager | None = None
        self._planner: Planner | None = None
        self._queue: ExecutionQueue | None = None
        self._collector: ResultCollector | None = None
        self._working_memory: WorkingMemory | None = None
        self._memory_system: MemorySystem | None = None
        self._event_buffer: deque[dict[str, Any]] = deque(maxlen=200)

    def mount(
        self,
        *,
        health_fn: Callable[[], HealthStatus],
        goal_manager: GoalManager,
        planner: Planner,
        queue: ExecutionQueue,
        collector: ResultCollector,
        working_memory: WorkingMemory,
        memory_system: MemorySystem,
        event_bus: EventBus,
    ) -> None:
        with self._lock:
            self._health_fn = health_fn
            self._goal_manager = goal_manager
            self._planner = planner
            self._queue = queue
            self._collector = collector
            self._working_memory = working_memory
            self._memory_system = memory_system

        # Subscribe to all events and buffer them
        event_bus.subscribe("*", self._on_event)

    def _on_event(self, event: Event) -> None:
        entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
        with self._lock:
            self._event_buffer.appendleft(entry)

    # ------------------------------------------------------------------
    # Read accessors (return copies — never live references)
    # ------------------------------------------------------------------

    def get_health(self) -> dict[str, Any] | None:
        if self._health_fn is None:
            return None
        h = self._health_fn()
        return {"state": h.state, "services": h.services}

    def get_goals(self) -> list[dict[str, Any]]:
        if self._goal_manager is None:
            return []
        return [g.model_dump(mode="json") for g in self._goal_manager.list()]

    def get_plans(self) -> list[dict[str, Any]]:
        if self._planner is None:
            return []
        # DefaultPlanner stores plans in _plans dict — read snapshot
        planner = self._planner
        if not hasattr(planner, "_plans"):
            return []
        with getattr(planner, "_lock", threading.Lock()):
            return [
                p.model_dump(mode="json")
                for p in planner._plans.values()  # noqa: SLF001
            ]

    def get_queue(self) -> dict[str, Any]:
        if self._queue is None:
            return {"pending": [], "running": [], "size": 0}
        snapshot = self._queue.snapshot()
        pending = [a.model_dump(mode="json") for a in self._queue.list_pending()]
        running = [a.model_dump(mode="json") for a in self._queue.list_running()]
        return {
            "pending": pending,
            "running": running,
            "size": snapshot.pending_count,
            "running_count": snapshot.running_count,
            "completed_count": snapshot.completed_count,
            "failed_count": snapshot.failed_count,
        }

    def get_running_action(self) -> dict[str, Any] | None:
        if self._queue is None:
            return None
        running = self._queue.list_running()
        if not running:
            return None
        return running[0].model_dump(mode="json")

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._collector is None:
            return []
        history = self._collector.history()
        recent = history[-limit:] if len(history) > limit else history
        return [
            {
                "observation_id": obs.observation_id,
                "action_id": obs.action_id,
                "plan_id": obs.plan_id,
                "success": obs.success,
                "execution_time_ms": obs.execution_time,
                "timestamp": obs.timestamp.isoformat() if obs.timestamp else None,
                "result_summary": obs.result_summary
                if isinstance(obs.result_summary, str)
                else str(obs.result_summary),
            }
            for obs in reversed(recent)
        ]

    def get_working_memory(self) -> list[dict[str, Any]]:
        if self._working_memory is None:
            return []
        return [i.model_dump(mode="json") for i in self._working_memory.active_items()]

    def get_long_term_memory(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._memory_system is None:
            return []
        try:
            results = self._memory_system.search(SearchQuery())
            recent = results[-limit:] if len(results) > limit else results
            return [e.model_dump(mode="json") for e in reversed(recent)]
        except Exception:
            return []

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._event_buffer)[:limit]

    def get_statistics(self) -> dict[str, Any]:
        if self._collector is None:
            return {}
        stats = self._collector.statistics()
        return {
            "total_executions": stats.total_executions,
            "successful_executions": stats.successful_executions,
            "failed_executions": stats.failed_executions,
            "average_duration_ms": round(stats.average_duration_ms, 2),
            "success_rate": round(stats.success_rate, 4),
            "failure_rate": round(stats.failure_rate, 4),
            "last_execution_time": stats.last_execution_time.isoformat()
            if stats.last_execution_time
            else None,
        }


# Singleton context
_ctx = _RuntimeContext()


def get_context() -> _RuntimeContext:
    """Returns the module-level runtime context singleton."""
    return _ctx


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAGE Runtime API",
    description="Read-only introspection API for the RAGE Cognitive Runtime",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    health = _ctx.get_health()
    if health is None:
        return {"state": "OFFLINE", "services": {}}
    return health


@app.get("/api/goals")
def get_goals() -> list[dict[str, Any]]:
    return _ctx.get_goals()


@app.get("/api/plans")
def get_plans() -> list[dict[str, Any]]:
    return _ctx.get_plans()


@app.get("/api/queue")
def get_queue() -> dict[str, Any]:
    return _ctx.get_queue()


@app.get("/api/executor")
def get_executor() -> dict[str, Any]:
    action = _ctx.get_running_action()
    return {"current_action": action}


@app.get("/api/history")
def get_history(limit: int = 50) -> list[dict[str, Any]]:
    return _ctx.get_history(limit=limit)


@app.get("/api/memory/working")
def get_working_memory() -> list[dict[str, Any]]:
    return _ctx.get_working_memory()


@app.get("/api/memory/long-term")
def get_long_term_memory(limit: int = 50) -> list[dict[str, Any]]:
    return _ctx.get_long_term_memory(limit=limit)


@app.get("/api/events")
def get_events(limit: int = 100) -> list[dict[str, Any]]:
    return _ctx.get_events(limit=limit)


@app.get("/api/statistics")
def get_statistics() -> dict[str, Any]:
    return _ctx.get_statistics()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}
