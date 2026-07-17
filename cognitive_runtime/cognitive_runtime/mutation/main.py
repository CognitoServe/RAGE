import sys

from cognitive_runtime.mutation.engine import run_mutation_on_file


def main():
    print("Running mutation tests...")

    # Define (source_file, test_file) pairs
    targets = [
        (
            "cognitive_runtime/events/bus.py",
            "tests/events/test_bus.py",
        ),
        (
            "cognitive_runtime/core/registry/registry.py",
            "tests/core/registry/test_registry.py",
        ),
        (
            "cognitive_runtime/knowledge/networkx_repository.py",
            "tests/knowledge/test_networkx.py",
        ),
        (
            "cognitive_runtime/memory/sqlite_repository.py",
            "tests/memory/test_sqlite.py",
        ),
        (
            "cognitive_runtime/rules/engine.py",
            "tests/rules/test_engine.py",
        ),
        (
            "cognitive_runtime/core/brain.py",
            "tests/core/test_brain.py",
        ),
        (
            "cognitive_runtime/goals/manager.py",
            "tests/goals/test_manager.py",
        ),
        (
            "cognitive_runtime/working_memory/system.py",
            "tests/working_memory/test_system.py",
        ),
    ]

    all_results = []
    print("Running mutation tests...")
    for target_file, test_file in targets:
        try:
            print(f"Mutating: {target_file}")
            results = run_mutation_on_file(target_file, test_file)
            all_results.extend(results)
        except Exception as e:
            print(f"Error mutating {target_file}: {e}", file=sys.stderr)

    total_mutants = len(all_results)
    killed_mutants = sum(1 for r in all_results if r["status"] == "KILLED")
    score = (killed_mutants / total_mutants * 100.0) if total_mutants > 0 else 0.0

    print("\n# Mutation Test Report")
    print(f"**Total Mutants:** {total_mutants}")
    print(f"**Mutants Killed:** {killed_mutants}")
    print(f"**Mutation Score:** {score:.2f}%")

    survived = [r for r in all_results if r["status"] == "SURVIVED"]
    if survived:
        print("\n## Survived Mutants (Weak Test Areas)")
        print("| File | Line | Mutation Description |")
        print("| :--- | :--- | :--- |")
        for s in survived:
            print(f"| {s['file']} | {s['line']} | {s['description']} |")
    else:
        print("\n## All Mutants Killed (100% Mutation Coverage!)")


if __name__ == "__main__":
    main()
