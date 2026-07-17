# Planner (RFC-0010)

The Planner is a core subsystem in the cognitive architecture. It exists to convert goals into executable plans.

## Goal vs. Decision vs. Plan
- **Goal**: Represents a desired end state or objective (e.g., "Build a house", "Find the error in this log"). Managed by the Goal Manager.
- **Decision**: Represents an autonomous choice about *what* goal to pursue next or *how* to allocate resources. Managed by the Decision Engine.
- **Plan**: Represents a concrete sequence of steps or a structured blueprint required to achieve a specific Goal. 

## Why the Planner Never Executes Actions
The Planner is strictly an analytical and structural subsystem. It builds the map, but it does not drive the car. 
Executing actions requires interacting with external environments, tools, or memory, which introduces side effects, latency, and partial failures. By keeping the Planner free of execution responsibilities, we ensure that:
1. Planning remains fast, thread-safe, and side-effect-free.
2. The execution layer can handle retries, timeouts, and sandboxing without complicating the planning logic.
3. A clear boundary is maintained between generating the steps and acting on them.

## Why Planning is Deterministic in Version 1
In Version 1 of this architecture, the Planner utilizes a `SequentialTemplateStrategy` that relies on static hierarchical task decomposition to generate sequential plans without branching. 
We strictly avoid A*, Goal-Oriented Action Planning (GOAP), Hierarchical Task Networks (HTN), or reinforcement learning models in V1 to:
- Guarantee predictability and baseline stability in the core loop.
- Establish a robust foundation and solid test coverage before introducing non-deterministic failure modes.
- Prove the event-driven integration between the Goal Manager, Planner, and Execution subsystems first.

Future versions may adopt dynamic replanning, constraint planning, and multi-agent planning. For now, the implementation remains deliberately constrained.
