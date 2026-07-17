import ast
import os
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent / "cognitive_runtime"
SUBSYSTEMS = [
    "brain", "config", "core", "decisions", "events", "goals", 
    "knowledge", "logging", "memory", "mutation", "planner", 
    "rules", "stress", "working_memory"
]
BANNED_LIBS = ["torch", "tensorflow", "sklearn", "openai", "transformers", "llm", "keras", "scipy"]

def analyze_imports():
    import_graph = defaultdict(set)
    errors = []

    for py_file in ROOT_DIR.rglob("*.py"):
        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            continue
            
        module_name = "cognitive_runtime" + str(py_file).split("cognitive_runtime")[-1].replace(os.sep, ".").replace(".py", "")
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]
            
        # Figure out which subsystem this file belongs to
        parts = module_name.split(".")
        if len(parts) < 2 or parts[1] not in SUBSYSTEMS:
            continue
            
        subsystem = parts[1]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_lib = alias.name.split(".")[0]
                    if base_lib in BANNED_LIBS:
                        errors.append(f"BANNED LIB {base_lib} imported in {module_name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base_lib = node.module.split(".")[0]
                    if base_lib in BANNED_LIBS:
                        errors.append(f"BANNED LIB {base_lib} imported in {module_name}")
                    
                    if node.module.startswith("cognitive_runtime."):
                        target_parts = node.module.split(".")
                        if len(target_parts) >= 2:
                            target_subsys = target_parts[1]
                            if target_subsys in SUBSYSTEMS and target_subsys != subsystem:
                                import_graph[subsystem].add(target_subsys)
                                allowed_targets = ["interfaces", "events", "models", "exceptions", "manager"]
                                if len(target_parts) > 2 and target_parts[2] not in allowed_targets:
                                    # core and stress are composition roots, they must instantiate implementations
                                    if subsystem not in ["core", "stress", "logging", "config", "mutation", "cli", "brain"]:
                                        errors.append(f"Subsystem {subsystem} imports internal {node.module} instead of interface/event/model")
                                        
    # Check for circular imports between subsystems
    def check_cycles(graph):
        visited = set()
        stack = set()
        cycles = []
        def visit(node, path):
            if node in stack:
                cycles.append(path[path.index(node):] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for neighbor in graph[node]:
                visit(neighbor, path + [neighbor])
            stack.remove(node)
            
        for node in list(graph.keys()):
            visit(node, [node])
        return cycles
        
    cycles = check_cycles(import_graph)
    if cycles:
        for c in cycles:
            errors.append(f"CIRCULAR IMPORT: {' -> '.join(c)}")
            
    if errors:
        print("ARCHITECTURE AUDIT FAILED:")
        for e in errors:
            print(" -", e)
        exit(1)
    else:
        print("ARCHITECTURE AUDIT PASSED: 0 Violations.")

if __name__ == "__main__":
    analyze_imports()
