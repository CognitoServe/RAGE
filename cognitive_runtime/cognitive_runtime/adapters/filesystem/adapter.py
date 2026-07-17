import shutil
import time
from pathlib import Path
from typing import Any

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult

from .events import (
    create_filesystem_operation_completed_event,
    create_filesystem_operation_failed_event,
    create_filesystem_operation_started_event,
    create_filesystem_validation_failed_event,
)
from .exceptions import FilesystemValidationError


class FilesystemAdapter(ActionAdapter):
    """
    Adapter for executing filesystem operations.
    Relies strictly on pathlib and shutil. Does not spawn subprocesses.
    """

    SUPPORTED_TYPES = {
        ActionType.FILE_READ,
        ActionType.FILE_WRITE,
        ActionType.FILE_MOVE,
        ActionType.FILE_COPY,
        ActionType.FILE_DELETE,
        ActionType.DIRECTORY_CREATE,
        ActionType.DIRECTORY_DELETE,
    }

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self.SUPPORTED_TYPES

    def validate(self, action: Action) -> None:
        if action.type not in self.SUPPORTED_TYPES:
            raise FilesystemValidationError(f"Unsupported action type: {action.type}")

        if not action.target:
            raise FilesystemValidationError("Target path is required.")

        # Ensure parameters dictionary exists
        params = action.parameters or {}

        if action.type == ActionType.FILE_WRITE and "content" not in params:
            raise FilesystemValidationError("FILE_WRITE requires 'content'.")

        if (
            action.type in (ActionType.FILE_MOVE, ActionType.FILE_COPY)
            and "destination" not in params
        ):
            raise FilesystemValidationError(
                f"{action.type.value} requires 'destination'."
            )

    def execute(self, action: Action) -> ExecutionResult:
        start_time = time.perf_counter()

        try:
            self.validate(action)
        except FilesystemValidationError as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_filesystem_validation_failed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    target=action.target,
                    reason=str(e),
                )
            )
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

        target_path = Path(action.target)  # type: ignore[arg-type]
        self._bus.publish(
            create_filesystem_operation_started_event(
                action_id=action.action_id,
                action_type=action.type.value,
                target=str(target_path),
            )
        )

        try:
            output = self._dispatch(action, target_path)
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_filesystem_operation_completed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    target=str(target_path),
                    duration_ms=duration,
                )
            )
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=True,
                output=output,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._bus.publish(
                create_filesystem_operation_failed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    target=str(target_path),
                    reason=error_msg,
                    duration_ms=duration,
                )
            )
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=False,
                error=error_msg,
                duration_ms=duration,
            )

    def _dispatch(self, action: Action, target_path: Path) -> dict[str, Any]:
        params = action.parameters or {}

        if action.type == ActionType.FILE_READ:
            return self._read(target_path)
        elif action.type == ActionType.FILE_WRITE:
            return self._write(target_path, params["content"])
        elif action.type == ActionType.FILE_MOVE:
            return self._move(target_path, Path(params["destination"]))
        elif action.type == ActionType.FILE_COPY:
            return self._copy(target_path, Path(params["destination"]))
        elif action.type == ActionType.FILE_DELETE:
            return self._delete_file(target_path)
        elif action.type == ActionType.DIRECTORY_CREATE:
            return self._mkdir(target_path)
        elif action.type == ActionType.DIRECTORY_DELETE:
            return self._rmdir(target_path)
        else:
            # Should be unreachable due to validate()
            raise FilesystemValidationError(f"Unhandled action type: {action.type}")

    def _read(self, path: Path) -> dict[str, Any]:
        if path.is_dir():
            raise IsADirectoryError(f"Cannot read file: {path} is a directory")
        content = path.read_text(encoding="utf-8")
        return {"content": content, "size": len(content)}

    def _write(self, path: Path, content: str) -> dict[str, Any]:
        if path.is_dir():
            raise IsADirectoryError(f"Cannot write file: {path} is a directory")
        # Ensure parent exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"bytes_written": len(content.encode("utf-8"))}

    def _move(self, src: Path, dst: Path) -> dict[str, Any]:
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        return {"destination": str(dst)}

    def _copy(self, src: Path, dst: Path) -> dict[str, Any]:
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        if src.is_dir():
            raise IsADirectoryError(f"Cannot copy file: {src} is a directory")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return {"destination": str(dst)}

    def _delete_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path.is_dir():
            raise IsADirectoryError(
                f"Cannot delete file: {path} is a directory. Use DIRECTORY_DELETE."
            )
        path.unlink()
        return {"deleted": True}

    def _mkdir(self, path: Path) -> dict[str, Any]:
        if path.is_file():
            raise NotADirectoryError(f"Cannot create directory: {path} is a file")
        path.mkdir(parents=True, exist_ok=True)
        return {"created": True}

    def _rmdir(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        if path.is_file():
            raise NotADirectoryError(
                f"Cannot delete directory: {path} is a file. Use FILE_DELETE."
            )
        shutil.rmtree(path)
        return {"deleted": True}
