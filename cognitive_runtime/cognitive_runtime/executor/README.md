# Executor — RFC-0013

## Overview

The Executor is the **orchestration layer** of the RAGE cognitive runtime. It
receives `Action` objects from the Execution Queue, resolves the correct
`ActionAdapter`, dispatches the action, and notifies the Queue of the outcome.

It contains **zero execution logic** — no filesystem, HTTP, process, or plugin
code. All of that lives in Action Adapters.

---

## Why Executor is separate from Queue

| Concern | Owner |
|---------|-------|
| Which action runs next? | Queue |
| What order do actions run in? | Queue |
| How is an action dispatched? | Executor |
| Which adapter handles this type? | Executor |
| Did the action succeed? | Executor (notifies Queue) |

The Queue knows nothing about adapters. The Executor knows nothing about
scheduling. A clean boundary means either can be replaced independently.

## Why Executor never performs execution logic

If the Executor contained filesystem code, it would need to change every time
a new `ActionType` was added. Adapters encapsulate that volatility. The
Executor only knows the `ActionAdapter` interface — a single method:
`execute(action) → ExecutionResult`.

## Why adapters own implementation details

Each `ActionAdapter` is a single-responsibility component. The Executor
resolves the adapter, calls it, and receives a structured result. It never
inspects the adapter's internals.

## Why orchestration is isolated

The Executor is pure coordination: validate → resolve → dispatch → notify →
publish. Every step is auditable and testable. Mixing any domain logic
(planning, memory, goals) into this layer would make it impossible to test
the orchestration in isolation.

---

## Architecture

```
Execution Queue
     │
     │ dequeue() → RUNNING action
     ▼
  Executor
     │
     │ register_adapter(type, adapter)
     │ resolve adapter by ActionType
     │ adapter.execute(action) → ExecutionResult
     │
     ▼
Action Adapter
     │
     ▼
Operating System / External World
```

The Executor never crosses the boundary marked by "Operating System". Only
adapters do.

---

## Dispatch Flow

Every call to `execute_next()` follows this exact sequence:

```
queue.dequeue()              → get a RUNNING action (or None)
execute(action)              → dispatch kernel:
  ├─ validate state          → must be RUNNING
  ├─ check duplicate guard   → action_id not in _executing
  ├─ resolve adapter         → _adapters[action.type]
  ├─ publish ExecutionStarted
  ├─ adapter.execute(action) → may raise; caught and wrapped
  ├─ update stats            → total, success/fail, time
  └─ publish Completed/Failed
queue.complete(action_id)    → on success
queue.fail(action_id, reason)→ on failure
return ExecutionResult
```

`execute(action)` is the inner kernel. It can be called directly (bypassing
the queue) for testing or direct dispatch scenarios. The caller is responsible
for notifying the queue of the outcome in that case.

---

## Public API

### `DefaultExecutor`

| Method | Description |
|--------|-------------|
| `start()` | Enter running state. Publishes `ExecutorStarted`. Idempotent. |
| `stop()` | Exit running state. Publishes `ExecutorStopped`. Idempotent. |
| `is_running()` | True if started and not stopped. |
| `submit(action)` | Enqueue an action. Delegates to `queue.enqueue()`. |
| `execute_next()` | Dequeue + dispatch + notify queue. Returns `ExecutionResult \| None`. |
| `execute(action)` | Dispatch a RUNNING action directly (no queue interaction). |
| `cancel(action_id)` | Delegates to `queue.cancel()`. |
| `register_adapter(type, adapter)` | Register an adapter for an ActionType. |
| `stats()` | Return `ExecutorStats` snapshot. |

### `ActionAdapter` (ABC)

| Method | Description |
|--------|-------------|
| `execute(action)` | Perform the work. Return `ExecutionResult`. May raise. |
| `supports(type)` | Return True if this adapter handles the given ActionType. |

---

## Events

| Event | Trigger |
|-------|---------|
| `ExecutorStarted` | `start()` on a stopped executor |
| `ExecutorStopped` | `stop()` on a running executor |
| `ActionExecutionStarted` | immediately before adapter call |
| `ActionExecutionCompleted` | adapter returned successfully |
| `ActionExecutionFailed` | adapter raised or dispatch was rejected |
| `AdapterResolutionFailed` | no adapter registered for ActionType |
| `UnsupportedActionType` | adapter registered but `supports()` returns False |

---

## Concurrency

V1 is single-consumer: one caller calls `execute_next()` at a time. The
executor does NOT spawn background threads. This is intentional — it keeps the
executor as a pure dispatcher that can be driven by any scheduling strategy.

A future `WorkerThread` class can wrap `DefaultExecutor` with a background loop
without modifying the executor itself.

The **duplicate-dispatch guard** (`_executing: set[str]`) prevents the same
`action_id` from being dispatched concurrently, even if multiple threads call
`execute()` with the same action. The guard is updated inside the RLock.

---

## Failure Handling

All adapter exceptions are caught by `execute()`. The executor:
1. Wraps the exception in `ExecutionResult(success=False, error=...)`
2. Publishes `ActionExecutionFailed`
3. Returns the failure result to the caller
4. Does NOT re-raise

This guarantees callers always receive a structured `ExecutionResult`, never
an unexpected exception from adapter internals.

---

## Observability (`ExecutorStats`)

| Field | Description |
|-------|-------------|
| `is_running` | Executor lifecycle state |
| `current_action_id` | action_id currently being dispatched, if any |
| `total_executed` | all dispatch attempts (success + failure) |
| `success_count` | successful dispatches |
| `failure_count` | failed dispatches (adapter raise or reject) |
| `average_execution_time_ms` | rolling average wall-clock time |
| `last_error` | most recent error message |

---

## Architecture Constraints (enforced by tests)

The executor module contains:
- ✅ Zero imports from `planner`, `goals`, `decisions`, `memory`, `knowledge`
- ✅ Zero `import os`, `import subprocess`, `import pathlib`
- ✅ Zero filesystem, HTTP, process, or plugin logic

These constraints are verified by `TestArchitectureConstraints` in the test suite.

---

## Usage Example

```python
from cognitive_runtime.executor import DefaultExecutor, ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult
from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.queue.queue import InMemoryExecutionQueue
from cognitive_runtime.events.bus import SynchronousEventBus

# Setup
bus = SynchronousEventBus()
queue = InMemoryExecutionQueue(bus)
executor = DefaultExecutor(queue=queue, event_bus=bus)

# Register adapters (temporary V1 registry — replaced by RFC-0014)
class MyFileAdapter(ActionAdapter):
    def execute(self, action: Action) -> ExecutionResult:
        # ... do file work ...
        return ExecutionResult(action_id=action.action_id, action_type=action.type, success=True)
    def supports(self, action_type: ActionType) -> bool:
        return action_type == ActionType.FILE_READ

executor.register_adapter(ActionType.FILE_READ, MyFileAdapter())
executor.start()

# Submit and run
action = Action(plan_id="p1", step_id="s1", type=ActionType.FILE_READ, target="/tmp/data.json")
executor.submit(action)
result = executor.execute_next()  # → ExecutionResult(success=True)

print(executor.stats())
```
