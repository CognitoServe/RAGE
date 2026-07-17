# Decision Engine Architecture

## Purpose
The Decision Engine is responsible for selecting *what* action the Cognitive Runtime should take based on the current active context (Working Memory and active Goals). 

## Why is it separate from the Planner?
In cognitive architectures, deciding *what* to do (intention) is fundamentally different from deciding *how* to do it (planning). 
- The **Decision Engine** evaluates facts and rules to produce a single deterministic intention (e.g., "Investigate Anomaly").
- The **Planner** takes that intention and breaks it down into executable, sequential steps.
Separating these concerns allows for distinct evaluation mechanisms. The Decision Engine can remain rule-based and deterministic, while the Planner can employ search algorithms (like A* or Monte Carlo Tree Search) to find optimal execution paths.

## Why are decisions deterministic in V0.1?
To establish a verifiable and safe baseline, V0.1 enforces a strict, deterministic rule-based policy. By avoiding probabilistic or machine-learning models, we guarantee that the same active context will always result in the same selected action. This is crucial for debugging, auditing, and establishing trust in the system's foundational logic before introducing non-deterministic models in later versions.

## Why do decisions never execute actions?
The Decision Engine follows the principle of pure functional boundaries. Its sole responsibility is to evaluate and produce a `Decision` artifact. Execution introduces side effects (e.g., network calls, state mutations) which can fail, block, or produce inconsistent states. By keeping the decision phase pure, we can safely simulate, replay, and audit decisions without unintended consequences. Execution is strictly delegated to the downstream Action Execution subsystem (not yet implemented in V0.1).
