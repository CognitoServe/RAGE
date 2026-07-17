from cognitive_runtime.stress.cases import (
    stress_event_bus,
    stress_knowledge,
    stress_memory,
    stress_registry,
)


def test_stress_cases_smoke():
    # Smoke test with low parameters to ensure execution correctness
    stress_event_bus(threads_count=2, iterations=5)
    stress_memory(threads_count=2, iterations=5)
    stress_knowledge(threads_count=2, iterations=5)
    stress_registry(threads_count=2, iterations=5)
