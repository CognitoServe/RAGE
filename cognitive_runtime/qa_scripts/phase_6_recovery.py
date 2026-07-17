import sys
from datetime import UTC, datetime

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.events.models import Event


def run_recovery_test():
    print("Starting Recovery Test...")
    brain = startup()
    bus = brain._services["EventBus"]
    
    # Track handlers
    executed = []
    
    def faulty_handler(event: Event):
        executed.append("faulty")
        raise RuntimeError("Simulated failure in handler")
        
    def good_handler(event: Event):
        executed.append("good")
        
    bus.subscribe("TestEvent", faulty_handler)
    bus.subscribe("TestEvent", good_handler)
    
    # Publish event
    event = Event(event_id="test_1", event_type="TestEvent", timestamp=datetime.now(UTC), source="test", payload={})
    bus.publish(event)
    
    if executed != ["faulty", "good"]:
        print(f"RECOVERY TEST FAILED. Expected both handlers to run despite exception. Got: {executed}")
        sys.exit(1)
        
    print("RECOVERY TEST PASSED: System gracefully recovered from handler exception.")
    shutdown(brain)

if __name__ == "__main__":
    run_recovery_test()
