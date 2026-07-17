from cognitive_runtime.benchmarks.runner import run_benchmark


def test_run_benchmark():
    def setup():
        return {"data": 123}

    def target(ctx):
        x = ctx["data"] + 1
        _ = x * x

    res = run_benchmark("Test case", setup, target, iterations=10)

    assert res["name"] == "Test case"
    assert res["avg"] >= 0
    assert res["median"] >= 0
    assert res["p95"] >= 0
    assert res["p99"] >= 0
    assert res["memory_usage_kb"] >= 0
    assert res["throughput"] > 0
