# 7. Working Memory Stress
import threading

from cognitive_runtime.events.bus import SynchronousEventBus


def stress_working_memory_extra(threads_count: int = 5, iterations: int = 2000):
    from cognitive_runtime.working_memory.models import ItemSource, WorkingMemoryItem
    from cognitive_runtime.working_memory.policies import LRUEvictionPolicy
    from cognitive_runtime.working_memory.system import DefaultWorkingMemory

    class StressTestFailureError(Exception):
        pass

    bus = SynchronousEventBus()
    policy = LRUEvictionPolicy()
    wm = DefaultWorkingMemory(bus, policy, capacity=20)
    exceptions = []

    def worker(tid):
        try:
            for i in range(iterations):
                item_id = f"item_{tid}_{i}"
                item = WorkingMemoryItem(
                    item_id=item_id, source=ItemSource.MEMORY, reference_id="ref"
                )
                wm.activate(item)

                # Retrieve
                if i % 2 == 0:
                    wm.contains(item_id)

                # Active items check
                if i % 10 == 0:
                    wm.active_items()

                # Deactivate early sometimes
                if i % 3 == 0:
                    wm.deactivate(item_id)

        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if exceptions:
        raise StressTestFailureError(f"Working Memory stress failed: {exceptions}")
