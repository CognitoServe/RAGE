# Result Collector — RFC-0016

## Overview

The `ResultCollector` is responsible for receiving `ExecutionResult`s produced by the `Executor` and converting them into structured runtime observations (`ExecutionObservation`s).

It closes the perception-action loop by observing what occurred during execution and feeding it back into the cognitive system.

## Why is it separate from the Executor?

The Executor is an orchestration engine. Its job is to figure out *how* to execute an Action (which Adapter to use, thread safety, retries, queues) and block until it finishes. If the Executor was also responsible for interacting with Memory, the Event Bus, and structuring cognitive observations, it would violate the Single Responsibility Principle and tightly couple action execution with memory systems.

By separating the Result Collector, the Executor remains focused purely on I/O orchestration.

## Immutability

`ExecutionResult`s and `ExecutionObservation`s are immutable (`frozen=True`). They represent historical facts—things that have already occurred. Once execution finishes, the record of that execution cannot be changed.

## Closing the Loop

An AI agent operates in a continuous loop:
1. Sense / Perceive
2. Think / Plan
3. Act / Execute
4. **Observe the result of the action**

The `ResultCollector` fulfills step 4. By taking the `ExecutionResult`, wrapping it in an `ExecutionObservation`, and pushing it into `WorkingMemory` and `MemorySystem` (Long-Term Memory), the cognitive engine can "perceive" what just happened, allowing it to evaluate if its plan succeeded and decide what to do next.

## Responsibilities
- Observes execution results.
- Translates results into cognitive observations.
- Maintains in-memory execution history and running statistics.
- Notifies Memory systems.
- Emits structured telemetry events.

## Boundaries
- Does NOT perform logic related to the OS (Filesystem, HTTP, etc.).
- Does NOT interact with Planners or Goals.
- Does NOT modify the `ExecutionResult`.
- Does NOT perform its own reasoning.
