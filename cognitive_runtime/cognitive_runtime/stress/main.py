import sys
import time

from cognitive_runtime.stress.cases import (
    stress_event_bus,
    stress_knowledge,
    stress_memory,
    stress_registry,
)


def run_scenario(name, func, threads, iterations):
    print(
        f"Running Stress Scenario: {name} ({threads} threads, {iterations} ops/thread)..."
    )
    t0 = time.perf_counter()
    try:
        func(threads_count=threads, iterations=iterations)
        duration = time.perf_counter() - t0
        print(f"PASS: {name} completed in {duration:.4f}s")
        return "PASS", duration, None
    except Exception as e:
        duration = time.perf_counter() - t0
        print(
            f"FAIL: {name} failed after {duration:.4f}s with error: {e}",
            file=sys.stderr,
        )
        return "FAIL", duration, str(e)


def main():
    from cognitive_runtime.stress.cases import (
        stress_goal_manager,
        stress_rule_engine,
        stress_working_memory,
    )

    scenarios = [
        ("Event Bus Concurrency", stress_event_bus, 10, 1000),
        ("Memory Concurrent Reads/Writes", stress_memory, 5, 200),
        ("Knowledge Graph Concurrency", stress_knowledge, 10, 1000),
        ("Service Registry Concurrency", stress_registry, 10, 1000),
        ("Rule Engine Concurrency", stress_rule_engine, 10, 1000),
        ("Goal Manager Concurrency", stress_goal_manager, 10, 1000),
        ("Working Memory Concurrency", stress_working_memory, 10, 1000),
    ]

    results = []
    for name, func, threads, iterations in scenarios:
        status, duration, error = run_scenario(name, func, threads, iterations)
        results.append((name, threads * iterations, status, duration, error))

    print(
        "\n| Scenario Name | Total Operations | Status | Duration (s) | Error / Anomaly |"
    )
    print("| :--- | :--- | :--- | :--- | :--- |")
    for name, total_ops, status, duration, error in results:
        err_msg = error if error else "None (Thread-Safe)"
        print(f"| {name} | {total_ops} | {status} | {duration:.4f} | {err_msg} |")


if __name__ == "__main__":
    main()
