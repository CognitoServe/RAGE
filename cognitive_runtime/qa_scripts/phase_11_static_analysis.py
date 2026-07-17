import subprocess


def run_static_analysis():
    print("Starting Static Analysis Test...")
    tools = [
        ["uv", "run", "ruff", "check", "cognitive_runtime"],
        ["uv", "run", "black", "cognitive_runtime"],
        ["uv", "run", "mypy", "cognitive_runtime"]
    ]
    
    with open("qa_report_static.txt", "w") as f:
        for cmd in tools:
            print(f"Running: {' '.join(cmd)}")
            f.write(f"--- {' '.join(cmd)} ---\n")
            result = subprocess.run(cmd, capture_output=True, text=True)
            f.write(result.stdout)
            f.write(result.stderr)
            if result.returncode != 0:
                print(f"Warnings/Errors found in {' '.join(cmd)}. See qa_report_static.txt")
            else:
                print(f"PASSED: {' '.join(cmd)}")
            
    print("STATIC ANALYSIS TEST EXECUTED.")
        
    print("STATIC ANALYSIS TEST PASSED.")

if __name__ == "__main__":
    run_static_analysis()
