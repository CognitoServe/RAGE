import sys

from cognitive_runtime.core.lifecycle import shutdown, startup

EXPECTED_SERVICES = [
    "EventBus",
    "ServiceRegistry",
    "MemorySystem",
    "KnowledgeSystem",
    "RuleEngine",
    "GoalManager",
    "WorkingMemory",
    "DecisionEngine",
    "Planner"
]

def run_boot_test():
    print("Starting Runtime Boot Test...")
    brain = startup()
    health = brain.health()
    
    services_found = list(health.services.keys())
    
    print("Services Initialized (In Order):")
    for s in services_found:
        print(f" - {s}")
        
    missing = [s for s in EXPECTED_SERVICES if s not in services_found]
    if missing:
        print(f"BOOT TEST FAILED. Missing services: {missing}")
        shutdown(brain)
        sys.exit(1)
        
    # Also verify order if possible, though health.services dict order in python 3.7+ is insertion order.
    # So if they match EXPECTED_SERVICES exactly in order, it's correct.
    for i, expected in enumerate(EXPECTED_SERVICES):
        if i >= len(services_found) or services_found[i] != expected:
            print(f"BOOT TEST FAILED. Expected {expected} at index {i}, found {services_found[i] if i < len(services_found) else 'Nothing'}")
            shutdown(brain)
            sys.exit(1)

    print("Boot sequence verified. Shutting down...")
    shutdown(brain)
    
    if brain.status().value != "STOPPED":
        print(f"BOOT TEST FAILED. Brain state is {brain.status()} instead of STOPPED")
        sys.exit(1)
        
    print("RUNTIME BOOT TEST PASSED.")
    
if __name__ == "__main__":
    run_boot_test()
