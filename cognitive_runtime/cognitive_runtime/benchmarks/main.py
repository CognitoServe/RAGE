import sys

from cognitive_runtime.benchmarks.bench_cases import (
    setup_event_publish,
    setup_knowledge_insert,
    setup_knowledge_lookup,
    setup_memory_insert,
    setup_memory_lookup,
    setup_neighbor_traversal,
    setup_registry_lookup,
    target_event_publish,
    target_knowledge_insert,
    target_knowledge_lookup,
    target_memory_insert,
    target_memory_lookup,
    target_neighbor_traversal,
    target_registry_lookup,
)
from cognitive_runtime.benchmarks.runner import run_benchmark


def main():
    cases = [
        ("Event Publish Latency", setup_event_publish, target_event_publish),
        ("Memory Insert", setup_memory_insert, target_memory_insert),
        ("Memory Lookup", setup_memory_lookup, target_memory_lookup),
        ("Knowledge Insert", setup_knowledge_insert, target_knowledge_insert),
        ("Knowledge Lookup", setup_knowledge_lookup, target_knowledge_lookup),
        ("Neighbor Traversal", setup_neighbor_traversal, target_neighbor_traversal),
        ("Service Registry Lookup", setup_registry_lookup, target_registry_lookup),
    ]

    results = []
    print("Running benchmarks (1000 iterations each)...")
    for name, setup, target in cases:
        try:
            res = run_benchmark(name, setup, target, iterations=1000)
            results.append(res)
            print(f"Finished: {name}")
        except Exception as e:
            print(f"Error running benchmark {name}: {e}", file=sys.stderr)

    print(
        "\n| Benchmark Name | Avg Latency (ms) | Median Latency (ms) | "
        "P95 (ms) | P99 (ms) | Memory Peak (KB) | Throughput (ops/s) |"
    )
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        print(
            f"| {r['name']} "
            f"| {r['avg']:.4f} "
            f"| {r['median']:.4f} "
            f"| {r['p95']:.4f} "
            f"| {r['p99']:.4f} "
            f"| {r['memory_usage_kb']:.2f} "
            f"| {r['throughput']:.2f} |"
        )


if __name__ == "__main__":
    main()
