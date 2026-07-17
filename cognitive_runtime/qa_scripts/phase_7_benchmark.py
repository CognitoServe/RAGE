import statistics
import timeit

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


def run_benchmark(name, setup_fn, target_fn, iterations=10000):
    ctx = setup_fn()
    
    # Run once to warm up
    if ctx is not None and isinstance(ctx, tuple):
        target_fn(ctx)
    else:
        target_fn(ctx)
        
    def run():
        if ctx is not None and isinstance(ctx, tuple):
            target_fn(ctx)
        else:
            target_fn(ctx)
            
    times = timeit.repeat(run, number=iterations, repeat=5)
    
    # average time per iteration in microseconds
    avg_us = (statistics.mean(times) / iterations) * 1_000_000
    stdev_us = (statistics.stdev(times) / iterations) * 1_000_000
    
    print(f"[{name.ljust(25)}] {avg_us:8.2f} µs/op  (+/- {stdev_us:6.2f} µs)")

def main():
    print("Starting Performance Benchmark (Phase 7)...")
    print("-" * 60)
    
    run_benchmark("Event Publish", setup_event_publish, target_event_publish)
    run_benchmark("Memory Insert", setup_memory_insert, target_memory_insert)
    run_benchmark("Memory Lookup", setup_memory_lookup, target_memory_lookup)
    run_benchmark("Knowledge Insert", setup_knowledge_insert, target_knowledge_insert)
    run_benchmark("Knowledge Lookup", setup_knowledge_lookup, target_knowledge_lookup)
    run_benchmark("Neighbor Traversal", setup_neighbor_traversal, target_neighbor_traversal)
    run_benchmark("Registry Lookup", setup_registry_lookup, target_registry_lookup)
    
    print("-" * 60)
    print("BENCHMARK TEST PASSED.")

if __name__ == "__main__":
    main()
