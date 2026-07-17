# Execution Queue — RFC-0012

## Overview

The Execution Queue is the **scheduling layer** of the RAGE cognitive runtime.
It sits between the Planner and a future Executor, accepting `Action` objects,
ordering them deterministically, and exposing them one at a time for dispatch.

It **never executes Actions**. It **never modifies Actions**. It **never touches the OS**.

---

## Design Rationale

### Why Queue is separate from Executor

The Queue's job is **ordering**: deciding what runs next and tracking lifecycle
state. The Executor's job is **dispatching**: calling the right adapter for a
given `ActionType`. Mixing these two concerns would couple scheduling policy to
execution implementation — you could not swap one without touching the other.

A pure scheduling queue can be tested end-to-end with zero external dependencies.
An executor can be built, replaced, or scaled independently without changing
the queue contract.

### Why scheduling is deterministic

**Priority-first / FIFO-within-priority** is a pure function of queue state:

- Sort key: `(-priority, sequence)`
- `sequence` is a monotonically incrementing integer assigned at `enqueue()` time
- No timestamps, no randomness, no heuristics

Given the same set of enqueued actions in the same insertion order, `dequeue()`
always returns the same action. This makes scheduling fully auditable and
testable with `assert` statements rather than probabilistic checks.

### Why the queue owns lifecycle but not execution

The queue maintains five internal buckets:

```
_pending   → waiting to be dispatched
_running   → dispatched, awaiting executor outcome
_completed → executor signalled SUCCESS
_failed    → executor signalled FAILURE (retry-eligible)
_cancelled → cancelled from any live bucket
```

When an executor finishes a dequeued Action, it calls `queue.complete(action_id)`
or `queue.fail(action_id, reason)`. The queue records the outcome and publishes
the event. The executor *causes* the outcome; the queue *records* it. This
separation of concerns means the queue remains a pure scheduling subsystem
regardless of what the executor does.

---

## State Machine

```
               ┌─────────┐
enqueue()  ──► │ PENDING │ (in queue, ordered)
               └────┬────┘
                    │ dequeue()
               ┌────▼────┐
               │ QUEUED  │ (status while in _pending bucket)
               └────┬────┘
                    │ dequeue() → moves to _running
               ┌────▼────┐
               │ RUNNING │ (dequeued, awaiting executor callback)
               └────┬────┘
        ┌───────────┼───────────┐
   complete()    fail()      cancel()
        │            │            │
   ┌────▼────┐  ┌────▼────┐  ┌───▼──────┐
   │ SUCCESS │  │ FAILED  │  │CANCELLED │
   └─────────┘  └────┬────┘  └──────────┘
                     │ retry()
                     └──► back to PENDING
```

Pending actions can also be cancelled directly.

---

## Public API

### `ExecutionQueue` (ABC)

| Method | Description |
|--------|-------------|
| `enqueue(action)` | Accept a PENDING action into the queue |
| `dequeue()` | Remove and return the next scheduled action (RUNNING) |
| `peek()` | Non-destructively view the next action |
| `cancel(action_id)` | Cancel a pending or running action |
| `retry(action_id)` | Re-enqueue a failed action (increments retry counter) |
| `complete(action_id)` | Executor callback: action succeeded |
| `fail(action_id, reason)` | Executor callback: action failed |
| `contains(action_id)` | True if tracked in any bucket |
| `size()` | Count of pending actions only |
| `clear()` | Empty the pending bucket |
| `list_pending()` | Snapshot of pending actions in scheduling order |
| `list_running()` | Snapshot of running actions |
| `list_completed()` | Snapshot of completed actions |
| `snapshot()` | `QueueSnapshot` with all bucket sizes |

---

## Events

| Event | Trigger | Source |
|-------|---------|--------|
| `ActionEnqueued` | `enqueue()` succeeds | `ExecutionQueue` |
| `ActionDequeued` | `dequeue()` removes an action | `ExecutionQueue` |
| `ActionRetried` | `retry()` re-enqueues a failed action | `ExecutionQueue` |
| `ActionQueueCleared` | `clear()` empties the pending bucket | `ExecutionQueue` |
| `ActionCompleted` | `complete()` is called by executor | `ActionModel` |
| `ActionFailed` | `fail()` is called by executor | `ActionModel` |
| `ActionCancelled` | `cancel()` or `clear()` removes an action | `ActionModel` |

---

## Scheduling Policy (V2)

- **Priority-first**: higher `action.priority` dequeues first.
- **FIFO within equal priority**: the monotonic `sequence` counter preserves insertion order.
- **Single consumer**: no parallel dequeue in V1. A future `ParallelExecutionQueue` can
  implement the same interface with a worker pool.

### Not implemented (future)
- Priority aging
- Dependency graphs / DAG execution
- Distributed queues
- Persistence / replay
- Dead-letter queues
- Back-pressure / capacity limits (hook: `QueueFullError` is defined)

---

## Usage Example

```python
from cognitive_runtime.queue import InMemoryExecutionQueue
from cognitive_runtime.actions import Action, ActionType
from cognitive_runtime.events.bus import SynchronousEventBus

bus = SynchronousEventBus()
queue = InMemoryExecutionQueue(bus)

# Producer (Planner side)
action = Action(
    plan_id="plan-001",
    step_id="step-001",
    type=ActionType.HTTP_GET,
    target="https://api.example.com/data",
    priority=10,
)
queue.enqueue(action)

# Consumer (Executor side)
next_action = queue.dequeue()  # status → RUNNING
if next_action:
    try:
        # ... execute ...
        queue.complete(next_action.action_id)
    except Exception as e:
        queue.fail(next_action.action_id, str(e))

# Retry a failed action
queue.retry(next_action.action_id)

# Introspection
snap = queue.snapshot()
print(f"Pending: {snap.pending_count}, Completed: {snap.completed_count}")
```

---

## Thread Safety

`InMemoryExecutionQueue` protects all shared state with a single `threading.RLock()`.
All five bucket mutations (append, pop, dict insert/remove) are performed inside
the lock. Events are published *outside* the lock to avoid holding it across
potentially slow handlers.

The RLock (reentrant) is used rather than a plain Lock to allow future refactoring
where methods call other methods on the same instance without deadlocking.
