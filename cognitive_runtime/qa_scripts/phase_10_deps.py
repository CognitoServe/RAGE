import subprocess
import sys


def run_deps_test():
    print("Starting Dependency Graph Generation Test...")
    # Run pydeps to just print deps without graphviz
    try:
        result = subprocess.run(
            ["uv", "run", "pydeps", "cognitive_runtime/core", "--show-deps", "--nodot"],
            capture_output=True, text=True, check=True
        )
        if "cognitive_runtime" in result.stdout:
            print("DEPENDENCY GRAPH PASSED: Parsed dependencies successfully.")
        else:
            print("DEPENDENCY GRAPH FAILED: Output did not contain expected modules.")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"DEPENDENCY GRAPH FAILED: {e.stderr}")
        sys.exit(1)
        
if __name__ == "__main__":
    run_deps_test()
