import os
import subprocess

from .mutators import generate_mutants


def run_mutation_on_file(target_file: str, test_file: str) -> list[dict]:
    """
    Injects mutants into target_file and runs test_file to verify if mutants are killed.
    """
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Target file {target_file} not found.")
    if not os.path.exists(test_file):
        raise FileNotFoundError(f"Test file {test_file} not found.")

    with open(target_file, encoding="utf-8") as f:
        original_content = f.read()

    mutants = generate_mutants(original_content)
    results = []

    for mutated_content, desc, line_num in mutants:
        try:
            # Write mutant
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(mutated_content)

            # Run pytest
            # We use standard subprocess run to invoke pytest on the test file
            res = subprocess.run(
                ["uv", "run", "pytest", test_file, "-q", "--tb=no"],
                capture_output=True,
                text=True,
            )

            status = "KILLED" if res.returncode != 0 else "SURVIVED"
            results.append(
                {
                    "file": os.path.basename(target_file),
                    "line": line_num,
                    "description": desc,
                    "status": status,
                }
            )
        finally:
            # Always restore original content to prevent code corruption
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(original_content)

    return results
