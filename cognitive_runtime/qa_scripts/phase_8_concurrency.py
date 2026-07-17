import random
import sys
import threading
import time
import uuid
from datetime import UTC, datetime

from cognitive_runtime.core.lifecycle import shutdown, startup
from cognitive_runtime.events.models import Event
from cognitive_runtime.goals.models import Goal, GoalStatus
from cognitive_runtime.knowledge.models import Fact


def run_concurrency_test(duration=5.0):
    print(f"Starting Thread Safety Test for {duration} seconds...")
    brain = startup()
    
    bus = brain._services["EventBus"]
    goals = brain._services["GoalManager"]
    knowledge = brain._services["KnowledgeSystem"]
    
    # Pre-create a goal to update
    base_goal_id = str(uuid.uuid4())
    goal = Goal(goal_id=base_goal_id, title="Base Goal", description="Concurrency", priority=1, status=GoalStatus.ACTIVE, created_at=datetime.now(UTC), metadata={})
    goals.create(goal)
    
    running = True
    errors = []
    
    def worker_thread(thread_id):
        nonlocal running
        try:
            while running:
                action = random.choice(["add_knowledge", "update_goal", "publish_event"])
                
                if action == "add_knowledge":
                    fact_id = str(uuid.uuid4())
                    knowledge.add_fact(Fact(fact_id=fact_id, subject=f"T{thread_id}", predicate="is", object="working", source="test"))
                    # also read
                    knowledge.exists(fact_id)
                    
                elif action == "update_goal":
                    # Fetch and update priority
                    current = goals.highest_priority()
                    if current:
                        updated = current.model_copy(update={"priority": random.randint(1, 10)})
                        goals.update(updated)
                        
                elif action == "publish_event":
                    bus.publish(Event(event_type="ThreadPing", source=f"T{thread_id}"))
                    
                # Small sleep to yield
                time.sleep(0.001)
        except Exception as e:
            errors.append((thread_id, e))

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker_thread, args=(i,))
        t.start()
        threads.append(t)
        
    time.sleep(duration)
    running = False
    
    for t in threads:
        t.join(timeout=2.0)
        if t.is_alive():
            print("THREAD SAFETY TEST FAILED: Deadlock detected (thread did not join)")
            sys.exit(1)
            
    if errors:
        print(f"THREAD SAFETY TEST FAILED: Exceptions in threads: {errors}")
        sys.exit(1)
        
    shutdown(brain)
    print("THREAD SAFETY TEST PASSED: No deadlocks or race conditions detected.")

if __name__ == "__main__":
    run_concurrency_test()
