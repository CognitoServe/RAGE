# Cognitive Runtime

A modular neuro-symbolic cognitive architecture.

## Version 0.1

This is the foundational project skeleton for version 0.1, designed with a strict interface-first, clean architecture in mind. 
It focuses solely on setting up the infrastructure required for the cognitive runtime to operate:
- Starting and stopping the runtime.
- Storing memories, facts, and rules.
- Publishing events.
- Writing logs.

## Tech Stack
- **Python:** 3.13+
- **Package Manager:** uv
- **Data Validation & Config:** Pydantic v2
- **Database:** SQLite
- **Graphs:** NetworkX
- **Logging:** structlog
- **Linting & Formatting:** Ruff
- **CLI:** Typer
- **Testing:** pytest

## Principles
1. Single Responsibility Principle.
2. Dependency Injection wherever appropriate.
3. Interface-first design.
4. Strong typing everywhere.
5. No global mutable state.
6. Every module must be independently testable.
7. Every public method must have docstrings.
8. Production-quality code only.
