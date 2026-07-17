# Action Model — RFC-0011

## Overview

The Action Model is the **universal executable instruction** used by RAGE.

It represents **WHAT** should be executed. It does not execute itself. It
contains no business logic, no reasoning, and no knowledge of the operating
system. It is immutable, serializable, and safely transportable between any
module in the cognitive runtime.

---

## Design Rationale

### Why is Action separate from Planner?

The `Planner` operates at the level of **intent**: it produces `Step` objects
that describe what needs to be accomplished in abstract, goal-oriented terms.
An `Action` translates that intent into a **concrete, typed, executable
descriptor** that can be passed to any execution layer.

This separation provides three key benefits:

1. **Replaceability**: The Planner algorithm can be changed (HTN, GOAP, LLM,
   etc.) without altering the execution contract.
2. **Testability**: Actions can be unit-tested in isolation from any planning
   or execution system.
3. **Transport safety**: Actions can be serialized, queued, and deserialized
   across process or network boundaries with zero loss of fidelity.

### Why is Action immutable?

Actions are **transport primitives**. Once created, every module that receives
an Action must see exactly the same data. If an Action could be mutated
mid-flight — e.g., a handler modifying its `target` or `parameters` — execution
would become non-deterministic and audit logs would become unreliable.

Pydantic's `ConfigDict(frozen=True)` enforces this at the language level:
any attempt to assign to a field raises a `ValidationError` immediately.

To advance an Action's lifecycle, use the `with_status()` helper, which
produces a **new** Action instance with the updated field:

```python
running_action = action.with_status(ActionStatus.RUNNING)
```

### Why does Action never perform execution?

An Action is **pure data**. Mixing execution logic into a data model:

- Violates the Single Responsibility Principle
- Ties the data structure to a specific OS/runtime environment
- Prevents the Action from being serialized or sent across module boundaries
- Makes unit testing significantly harder

All execution belongs in a future `Executor` module that *receives* Actions
and acts upon them.

---

## Public API

### `ActionType` (StrEnum)

```
FILE_READ, FILE_WRITE, FILE_MOVE, FILE_COPY, FILE_DELETE
DIRECTORY_CREATE, DIRECTORY_DELETE
HTTP_GET, HTTP_POST
PROCESS_START, PROCESS_STOP
PLUGIN_CALL
CUSTOM
```

### `ActionStatus` (StrEnum)

```
PENDING → QUEUED → RUNNING → SUCCESS
                           → FAILED
                           → TIMEOUT
Any non-terminal → CANCELLED
```

### `Action` fields

| Field          | Type                 | Required | Description                                |
|----------------|----------------------|----------|--------------------------------------------|
| `action_id`    | `str`                | auto     | UUID, auto-generated                       |
| `plan_id`      | `str`                | ✓        | Correlation ID of the parent Plan          |
| `step_id`      | `str`                | ✓        | Correlation ID of the parent Step          |
| `type`         | `ActionType`         | ✓        | Category of operation                      |
| `target`       | `str`                | ✓        | Path, URL, process name, plugin ID, etc.   |
| `parameters`   | `dict[str, Any]`     | auto     | Type-specific parameters, default `{}`     |
| `priority`     | `int`                | auto     | Execution priority, default `0`            |
| `status`       | `ActionStatus`       | auto     | Starts at `PENDING`                        |
| `created_at`   | `datetime`           | auto     | UTC timestamp, auto-generated              |
| `scheduled_at` | `datetime \| None`   | —        | Optional deferred execution time           |
| `started_at`   | `datetime \| None`   | —        | Set by executor when execution begins      |
| `completed_at` | `datetime \| None`   | —        | Set by executor when execution ends        |
| `metadata`     | `dict[str, Any]`     | auto     | Arbitrary annotations, default `{}`        |

### `ActionResultReference` fields

A lightweight pointer to where a result is stored — **not** the result itself.

| Field       | Type             | Required | Description                            |
|-------------|------------------|----------|----------------------------------------|
| `action_id` | `str`            | ✓        | The action whose result this describes |
| `store`     | `str`            | ✓        | Store name (e.g., `"working_memory"`)  |
| `key`       | `str`            | ✓        | Key or path within the store           |
| `metadata`  | `dict[str, Any]` | auto     | Annotations (size, content-type, etc.) |

---

## Events

All events are produced by factory functions in `events.py` and published via
the `EventBus`. No action lifecycle event carries the full Action payload —
only the `action_id` and essential correlation data.

| Event Type        | When                                          |
|-------------------|-----------------------------------------------|
| `ActionCreated`   | A new Action is built from a plan step        |
| `ActionQueued`    | The Action enters the execution queue         |
| `ActionStarted`   | An executor begins processing it              |
| `ActionCompleted` | Executor reports success                      |
| `ActionFailed`    | Executor reports failure                      |
| `ActionCancelled` | Action is cancelled before/during execution   |

---

## Usage Example

```python
from cognitive_runtime.actions import Action, ActionType, ActionStatus

# Create a read action
action = Action(
    plan_id="plan-abc",
    step_id="step-001",
    type=ActionType.FILE_READ,
    target="/var/data/input.json",
    parameters={"encoding": "utf-8"},
    priority=10,
)

# Check state
assert action.status == ActionStatus.PENDING
assert not action.is_terminal()
assert action.can_transition_to(ActionStatus.QUEUED)

# Advance lifecycle (produces a new Action — original is unchanged)
queued = action.with_status(ActionStatus.QUEUED)
assert queued.status == ActionStatus.QUEUED
assert action.status == ActionStatus.PENDING  # original untouched

# Serialize / deserialize
data = action.model_dump(mode="json")
restored = Action.model_validate(data)
assert restored == action
```

---

## Constraints

- Actions **never** execute themselves.
- Actions **never** import from `planner`, `goals`, `decisions`, or `memory`.
- Actions **never** reference the operating system.
- Mutation via field assignment is **impossible** (`frozen=True`).
- The `target` and `parameters` schema is **enforced by the executor**, not here.
