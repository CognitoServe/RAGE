"""
Tests for RFC-0014 — Filesystem Adapter

Coverage:
1. Validation constraints (missing target, unsupported type, missing params)
2. FILE_READ (success, missing file, reading a dir)
3. FILE_WRITE (success, overwriting, writing to a dir)
4. FILE_MOVE (success, missing source)
5. FILE_COPY (success, missing source, copying a dir)
6. FILE_DELETE (success, missing file, deleting a dir)
7. DIRECTORY_CREATE (success, creating over a file)
8. DIRECTORY_DELETE (success, missing dir, deleting a file)
9. Event publication (Started, Completed, Failed, ValidationFailed)
10. Architecture constraints (no forbidden imports)
"""

import threading
from pathlib import Path
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionStatus, ActionType
from cognitive_runtime.adapters.filesystem.adapter import FilesystemAdapter
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
        "action_id": "test-act-001",
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
def adapter(bus: CapturingEventBus) -> FilesystemAdapter:
    return FilesystemAdapter(event_bus=bus)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_unsupported_type(self, adapter: FilesystemAdapter) -> None:
        action = make_action(ActionType.HTTP_GET, target="http://example.com")
        result = adapter.execute(action)
        assert result.success is False
        assert "Unsupported action type" in result.error

    def test_missing_target(self, adapter: FilesystemAdapter) -> None:
        action = make_action(ActionType.FILE_READ, target="")
        result = adapter.execute(action)
        assert result.success is False
        assert "Target path is required" in result.error

    def test_file_write_missing_content(self, adapter: FilesystemAdapter) -> None:
        action = make_action(ActionType.FILE_WRITE, target="/tmp/test.txt")
        result = adapter.execute(action)
        assert result.success is False
        assert "requires 'content'" in result.error

    def test_file_copy_missing_destination(self, adapter: FilesystemAdapter) -> None:
        action = make_action(ActionType.FILE_COPY, target="/tmp/src.txt")
        result = adapter.execute(action)
        assert result.success is False
        assert "requires 'destination'" in result.error

    def test_file_move_missing_destination(self, adapter: FilesystemAdapter) -> None:
        action = make_action(ActionType.FILE_MOVE, target="/tmp/src.txt")
        result = adapter.execute(action)
        assert result.success is False
        assert "requires 'destination'" in result.error


# ---------------------------------------------------------------------------
# 2. FILE_READ
# ---------------------------------------------------------------------------

class TestFileRead:
    def test_read_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("hello world")
        action = make_action(ActionType.FILE_READ, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is True
        assert result.output["content"] == "hello world"
        assert result.output["size"] == 11

    def test_read_missing_file(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "missing.txt"
        action = make_action(ActionType.FILE_READ, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "FileNotFoundError" in result.error

    def test_read_directory(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "somedir"
        dir_path.mkdir()
        action = make_action(ActionType.FILE_READ, target=str(dir_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "IsADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 3. FILE_WRITE
# ---------------------------------------------------------------------------

class TestFileWrite:
    def test_write_success_and_creates_parents(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "nested" / "test.txt"
        action = make_action(ActionType.FILE_WRITE, target=str(file_path), parameters={"content": "written"})
        result = adapter.execute(action)
        assert result.success is True
        assert file_path.read_text() == "written"

    def test_write_overwrites(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("old")
        action = make_action(ActionType.FILE_WRITE, target=str(file_path), parameters={"content": "new"})
        result = adapter.execute(action)
        assert result.success is True
        assert file_path.read_text() == "new"

    def test_write_to_directory(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "somedir"
        dir_path.mkdir()
        action = make_action(ActionType.FILE_WRITE, target=str(dir_path), parameters={"content": "data"})
        result = adapter.execute(action)
        assert result.success is False
        assert "IsADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 4. FILE_MOVE
# ---------------------------------------------------------------------------

class TestFileMove:
    def test_move_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        src = temp_dir / "src.txt"
        src.write_text("data")
        dst = temp_dir / "dst.txt"
        action = make_action(ActionType.FILE_MOVE, target=str(src), parameters={"destination": str(dst)})
        result = adapter.execute(action)
        assert result.success is True
        assert not src.exists()
        assert dst.read_text() == "data"

    def test_move_missing_source(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        src = temp_dir / "missing.txt"
        dst = temp_dir / "dst.txt"
        action = make_action(ActionType.FILE_MOVE, target=str(src), parameters={"destination": str(dst)})
        result = adapter.execute(action)
        assert result.success is False
        assert "FileNotFoundError" in result.error


# ---------------------------------------------------------------------------
# 5. FILE_COPY
# ---------------------------------------------------------------------------

class TestFileCopy:
    def test_copy_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        src = temp_dir / "src.txt"
        src.write_text("data")
        dst = temp_dir / "dst.txt"
        action = make_action(ActionType.FILE_COPY, target=str(src), parameters={"destination": str(dst)})
        result = adapter.execute(action)
        assert result.success is True
        assert src.exists()
        assert dst.read_text() == "data"

    def test_copy_missing_source(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        src = temp_dir / "missing.txt"
        dst = temp_dir / "dst.txt"
        action = make_action(ActionType.FILE_COPY, target=str(src), parameters={"destination": str(dst)})
        result = adapter.execute(action)
        assert result.success is False
        assert "FileNotFoundError" in result.error

    def test_copy_directory(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        src = temp_dir / "somedir"
        src.mkdir()
        dst = temp_dir / "dst"
        action = make_action(ActionType.FILE_COPY, target=str(src), parameters={"destination": str(dst)})
        result = adapter.execute(action)
        assert result.success is False
        assert "IsADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 6. FILE_DELETE
# ---------------------------------------------------------------------------

class TestFileDelete:
    def test_delete_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("data")
        action = make_action(ActionType.FILE_DELETE, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is True
        assert not file_path.exists()

    def test_delete_missing_file(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "missing.txt"
        action = make_action(ActionType.FILE_DELETE, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "FileNotFoundError" in result.error

    def test_delete_directory(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "somedir"
        dir_path.mkdir()
        action = make_action(ActionType.FILE_DELETE, target=str(dir_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "IsADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 7. DIRECTORY_CREATE
# ---------------------------------------------------------------------------

class TestDirectoryCreate:
    def test_mkdir_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "nested" / "dir"
        action = make_action(ActionType.DIRECTORY_CREATE, target=str(dir_path))
        result = adapter.execute(action)
        assert result.success is True
        assert dir_path.is_dir()

    def test_mkdir_over_file(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("data")
        action = make_action(ActionType.DIRECTORY_CREATE, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "NotADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 8. DIRECTORY_DELETE
# ---------------------------------------------------------------------------

class TestDirectoryDelete:
    def test_rmdir_success(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "nested"
        dir_path.mkdir()
        (dir_path / "test.txt").write_text("data")
        action = make_action(ActionType.DIRECTORY_DELETE, target=str(dir_path))
        result = adapter.execute(action)
        assert result.success is True
        assert not dir_path.exists()

    def test_rmdir_missing(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        dir_path = temp_dir / "missing"
        action = make_action(ActionType.DIRECTORY_DELETE, target=str(dir_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "FileNotFoundError" in result.error

    def test_rmdir_on_file(self, adapter: FilesystemAdapter, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("data")
        action = make_action(ActionType.DIRECTORY_DELETE, target=str(file_path))
        result = adapter.execute(action)
        assert result.success is False
        assert "NotADirectoryError" in result.error


# ---------------------------------------------------------------------------
# 9. Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_events_on_success(self, adapter: FilesystemAdapter, bus: CapturingEventBus, temp_dir: Path) -> None:
        file_path = temp_dir / "test.txt"
        file_path.write_text("data")
        action = make_action(ActionType.FILE_READ, target=str(file_path))
        adapter.execute(action)
        
        started = bus.of_type("FilesystemOperationStarted")
        assert len(started) == 1
        assert started[0].payload["action_type"] == ActionType.FILE_READ.value
        
        completed = bus.of_type("FilesystemOperationCompleted")
        assert len(completed) == 1
        assert completed[0].payload["action_type"] == ActionType.FILE_READ.value
        assert "duration_ms" in completed[0].payload

    def test_events_on_failure(self, adapter: FilesystemAdapter, bus: CapturingEventBus, temp_dir: Path) -> None:
        file_path = temp_dir / "missing.txt"
        action = make_action(ActionType.FILE_READ, target=str(file_path))
        adapter.execute(action)
        
        started = bus.of_type("FilesystemOperationStarted")
        assert len(started) == 1
        
        failed = bus.of_type("FilesystemOperationFailed")
        assert len(failed) == 1
        assert "FileNotFoundError" in failed[0].payload["reason"]

    def test_events_on_validation_failure(self, adapter: FilesystemAdapter, bus: CapturingEventBus) -> None:
        action = make_action(ActionType.FILE_WRITE, target="/tmp/test.txt") # missing content
        adapter.execute(action)
        
        # Never started the actual OS op
        assert len(bus.of_type("FilesystemOperationStarted")) == 0
        
        validation_failed = bus.of_type("FilesystemValidationFailed")
        assert len(validation_failed) == 1
        assert "requires 'content'" in validation_failed[0].payload["reason"]


# ---------------------------------------------------------------------------
# 10. Architecture Constraints
# ---------------------------------------------------------------------------

class TestArchitectureConstraints:
    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.filesystem.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.planner" not in source
        assert "import planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.filesystem.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.goals" not in source

    def test_no_memory_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.filesystem.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.memory" not in source
        assert "from cognitive_runtime.working_memory" not in source

    def test_no_knowledge_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.filesystem.adapter as mod
        source = inspect.getsource(mod)
        assert "from cognitive_runtime.knowledge" not in source

    def test_no_os_module_import(self) -> None:
        import inspect

        import cognitive_runtime.adapters.filesystem.adapter as mod
        source = inspect.getsource(mod)
        # Should only use pathlib/shutil, not raw os methods for file ops
        assert "import os" not in source
        assert "import subprocess" not in source
