import statistics
import time
import tracemalloc
from collections.abc import Callable
from typing import Any


def run_benchmark(
    name: str,
    setup_func: Callable[[], Any],
    target_func: Callable[[Any], None],
    teardown_func: Callable[[Any], None] | None = None,
    iterations: int = 1000,
) -> dict[str, Any]:
    """
    Runs a benchmark target repeatedly, measuring latency, memory usage, and throughput.
    """
    context = setup_func()

    # Warmup
    for _ in range(5):
        target_func(context)

    latencies = []

    tracemalloc.start()

    start_time = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        target_func(context)
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1_000_000.0)  # to ms

    end_time = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if teardown_func:
        teardown_func(context)

    duration = end_time - start_time
    throughput = iterations / duration if duration > 0 else 0.0

    latencies.sort()
    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    p95_latency = latencies[int(len(latencies) * 0.95)] if len(latencies) > 0 else 0.0
    p99_latency = latencies[int(len(latencies) * 0.99)] if len(latencies) > 0 else 0.0

    return {
        "name": name,
        "avg": avg_latency,
        "median": median_latency,
        "p95": p95_latency,
        "p99": p99_latency,
        "memory_usage_kb": peak / 1024.0,
        "throughput": throughput,
    }
