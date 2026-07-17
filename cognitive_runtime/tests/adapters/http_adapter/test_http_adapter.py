"""
Tests for RFC-0015 — HTTP Adapter

Coverage:
1. Validation (missing target, malformed URL, invalid headers/timeout)
2. Execution (HTTP_GET, HTTP_POST, timeout)
3. HTTP Status Codes (200, 404, 500)
4. Network Errors (DNS failure, connection timeout)
5. Event publication (Started, Completed, Failed, ValidationFailed)
6. Architecture constraints (no forbidden imports)
"""

import http.server
import json
import threading
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionStatus, ActionType
from cognitive_runtime.adapters.http_adapter.adapter import HttpAdapter
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event


class CapturingEventBus(EventBus):
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)

    def subscribe(self, event_type: str, handler: Any) -> None:
        pass

    def unsubscribe(self, event_type: str, handler: Any) -> None:
        pass

    def of_type(self, event_type: str) -> list[Event]:
        with self._lock:
            return [e for e in self.events if e.event_type == event_type]


def make_action(
    action_type: ActionType,
    target: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Action:
    kwargs: dict[str, Any] = {
        "action_id": "test-http-001",
        "plan_id": "plan-001",
        "step_id": "step-001",
        "type": action_type,
        "priority": 0,
        "status": ActionStatus.RUNNING,
    }
    if target is not None:
        kwargs["target"] = target
    if parameters is not None:
        kwargs["parameters"] = parameters
    return Action(**kwargs)


@pytest.fixture
def bus() -> CapturingEventBus:
    return CapturingEventBus()


@pytest.fixture
def adapter(bus: CapturingEventBus) -> HttpAdapter:
    return HttpAdapter(event_bus=bus)


# --- Local Test Server ---

class DummyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"hello world")
        elif self.path == "/404":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not found")
        elif self.path == "/500":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"server error")
        elif self.path == "/timeout":
            import time
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(400)
            self.end_headers()
            
    def do_POST(self) -> None:
        if self.path == "/echo":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            
            self.send_response(200)
            self.send_header("Content-Type", self.headers.get("Content-Type", "text/plain"))
            self.end_headers()
            self.wfile.write(b"echo: " + body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Silence server logs


@pytest.fixture(scope="session")
def test_server() -> str:
    server = http.server.HTTPServer(("127.0.0.1", 0), DummyHTTPRequestHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ---------------------------------------------------------------------------
# 1. Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_unsupported_type(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.FILE_READ, target="http://example.com")
        result = adapter.execute(action)
        assert result.success is False
        assert "Unsupported action type" in result.error

    def test_missing_target(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="")
        result = adapter.execute(action)
        assert result.success is False
        assert "Target URL is required" in result.error

    def test_invalid_scheme(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="ftp://example.com")
        result = adapter.execute(action)
        assert result.success is False
        assert "must start with http://" in result.error

    def test_invalid_headers_type(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="http://example.com", parameters={"headers": "invalid"})
        result = adapter.execute(action)
        assert result.success is False
        assert "'headers' parameter must be a dictionary" in result.error

    def test_invalid_timeout_type(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="http://example.com", parameters={"timeout": "10s"})
        result = adapter.execute(action)
        assert result.success is False
        assert "'timeout' parameter must be a number" in result.error


# ---------------------------------------------------------------------------
# 2. Execution & Status Codes
# ---------------------------------------------------------------------------

class TestExecution:
    def test_http_get_200(self, adapter: HttpAdapter, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/")
        result = adapter.execute(action)
        assert result.success is True
        assert result.output is not None
        assert result.output["status_code"] == 200
        assert result.output["body"] == "hello world"

    def test_http_post_echo(self, adapter: HttpAdapter, test_server: str) -> None:
        action = make_action(
            ActionType.HTTP_POST, 
            target=f"{test_server}/echo", 
            parameters={"body": {"key": "value"}}
        )
        result = adapter.execute(action)
        assert result.success is True
        assert result.output is not None
        assert result.output["status_code"] == 200
        assert result.output["body"] == f"echo: {json.dumps({'key': 'value'})}"
        assert result.output["content_type"] == "application/json"

    def test_http_get_404(self, adapter: HttpAdapter, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/404")
        result = adapter.execute(action)
        # RFC specifies HTTP statuses are recorded in ExecutionResult. 
        # A 404 is a successful network exchange from the client's perspective.
        assert result.success is True
        assert result.output is not None
        assert result.output["status_code"] == 404
        assert result.output["body"] == "not found"

    def test_http_get_500(self, adapter: HttpAdapter, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/500")
        result = adapter.execute(action)
        assert result.success is True
        assert result.output is not None
        assert result.output["status_code"] == 500
        assert result.output["body"] == "server error"


# ---------------------------------------------------------------------------
# 3. Network Errors
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    def test_dns_failure(self, adapter: HttpAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="http://this-domain-does-not-exist.invalid")
        result = adapter.execute(action)
        assert result.success is False
        assert "URLError" in result.error

    def test_timeout_failure(self, adapter: HttpAdapter, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/timeout", parameters={"timeout": 0.1})
        result = adapter.execute(action)
        assert result.success is False
        # timeout is commonly URLError or TimeoutError depending on the underlying socket
        assert ("timeout" in result.error.lower() or "URLError" in result.error)


# ---------------------------------------------------------------------------
# 4. Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_events_on_success(self, adapter: HttpAdapter, bus: CapturingEventBus, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/")
        adapter.execute(action)
        
        started = bus.of_type("HttpRequestStarted")
        assert len(started) == 1
        assert started[0].payload["action_type"] == ActionType.HTTP_GET.value
        
        completed = bus.of_type("HttpRequestCompleted")
        assert len(completed) == 1
        assert completed[0].payload["action_type"] == ActionType.HTTP_GET.value
        assert completed[0].payload["status_code"] == 200
        assert "duration_ms" in completed[0].payload

    def test_events_on_404(self, adapter: HttpAdapter, bus: CapturingEventBus, test_server: str) -> None:
        action = make_action(ActionType.HTTP_GET, target=f"{test_server}/404")
        adapter.execute(action)
        
        # Should record HttpRequestCompleted with 404 status
        completed = bus.of_type("HttpRequestCompleted")
        assert len(completed) == 1
        assert completed[0].payload["status_code"] == 404

    def test_events_on_network_failure(self, adapter: HttpAdapter, bus: CapturingEventBus) -> None:
        action = make_action(ActionType.HTTP_GET, target="http://invalid.local")
        adapter.execute(action)
        
        started = bus.of_type("HttpRequestStarted")
        assert len(started) == 1
        
        failed = bus.of_type("HttpRequestFailed")
        assert len(failed) == 1
        assert "URLError" in failed[0].payload["reason"]

    def test_events_on_validation_failure(self, adapter: HttpAdapter, bus: CapturingEventBus) -> None:
        action = make_action(ActionType.HTTP_GET, target="ftp://example.com")
        adapter.execute(action)
        
        assert len(bus.of_type("HttpRequestStarted")) == 0
        
        validation_failed = bus.of_type("HttpValidationFailed")
        assert len(validation_failed) == 1
        assert "must start with http" in validation_failed[0].payload["reason"]


# ---------------------------------------------------------------------------
# 5. Architecture Constraints
# ---------------------------------------------------------------------------

class TestArchitectureConstraints:
    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.http_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.planner" not in source
        assert "import planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.http_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.goals" not in source

    def test_no_memory_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.http_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.memory" not in source
        assert "from cognitive_runtime.working_memory" not in source

    def test_no_knowledge_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.http_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.knowledge" not in source

    def test_no_queue_or_executor_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.http_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.queue" not in source
        assert "from cognitive_runtime.executor.executor" not in source
