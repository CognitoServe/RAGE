import os
import signal
import subprocess
import time
from typing import Any

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult

from .events import (
    create_process_completed_event,
    create_process_failed_event,
    create_process_started_event,
    create_process_validation_failed_event,
)
from .exceptions import ProcessValidationError


class ProcessAdapter(ActionAdapter):
    """
    Adapter for executing operating system processes.
    Strictly forbids running through a shell and handles OS-level errors gracefully.
    """

    SUPPORTED_TYPES = {
        ActionType.PROCESS_START,
        ActionType.PROCESS_STOP,
    }

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self.SUPPORTED_TYPES

    def validate(self, action: Action) -> None:
        if action.type not in self.SUPPORTED_TYPES:
            raise ProcessValidationError(f"Unsupported action type: {action.type}")

        if not action.target:
            raise ProcessValidationError("Target is required.")

        params = action.parameters or {}

        if action.type == ActionType.PROCESS_START:
            if "args" in params and not isinstance(params["args"], list):
                raise ProcessValidationError(
                    "'args' parameter must be a list of strings."
                )
            if "cwd" in params and not isinstance(params["cwd"], str):
                raise ProcessValidationError("'cwd' parameter must be a string.")
            if "env" in params and not isinstance(params["env"], dict):
                raise ProcessValidationError("'env' parameter must be a dictionary.")

        if "timeout" in params and not isinstance(params["timeout"], (int, float)):
            raise ProcessValidationError("'timeout' parameter must be a number.")

    def execute(self, action: Action) -> ExecutionResult:
        start_time = time.perf_counter()

        try:
            self.validate(action)
        except ProcessValidationError as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_process_validation_failed_event(
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

        params = action.parameters or {}
        args = params.get("args", [])

        self._bus.publish(
            create_process_started_event(
                action_id=action.action_id,
                action_type=action.type.value,
                target=action.target,
                args=args,
            )
        )

        try:
            if action.type == ActionType.PROCESS_START:
                output = self._execute_start(action, params)
            else:
                output = self._execute_stop(action, params)

            duration = (time.perf_counter() - start_time) * 1000
            success = output["exit_code"] == 0

            self._bus.publish(
                create_process_completed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    target=action.target,
                    exit_code=output["exit_code"],
                    duration_ms=duration,
                )
            )

            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=success,
                output=output,
                error=output.get("stderr") if not success else None,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"

            self._bus.publish(
                create_process_failed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    target=action.target,
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

    def _execute_start(self, action: Action, params: dict[str, Any]) -> dict[str, Any]:
        executable = action.target
        args = params.get("args", [])
        cwd = params.get("cwd")
        env = params.get("env")
        timeout = params.get("timeout", 30.0)

        cmd = [executable] + args

        # Run process synchronously. shell is omitted (defaults to False).
        # We explicitly capture stdout and stderr as strings (text=True).
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )

            return {
                "process_id": -1,  # We don't easily have the PID after run finishes
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "working_directory": cwd or os.getcwd(),
            }
        except FileNotFoundError as e:
            raise RuntimeError(f"Executable not found: {executable}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Process timed out after {timeout} seconds") from e

    def _execute_stop(self, action: Action, _params: dict[str, Any]) -> dict[str, Any]:
        try:
            pid = int(action.target)
        except ValueError as e:
            raise ProcessValidationError(
                "PROCESS_STOP target must be a valid integer PID."
            ) from e

        # Attempt to terminate the process gracefully
        try:
            # On Windows, SIGTERM behaves similarly to TerminateProcess
            os.kill(pid, signal.SIGTERM)
            exit_code = 0
            stderr = ""
        except ProcessLookupError:
            exit_code = 1
            stderr = f"Process {pid} not found."
        except OSError as e:
            # On Windows, killing a non-existent process can raise OSError
            exit_code = 1
            stderr = f"Failed to stop process {pid}: {str(e)}"

        return {
            "process_id": pid,
            "exit_code": exit_code,
            "stdout": "",
            "stderr": stderr,
            "working_directory": os.getcwd(),
        }
