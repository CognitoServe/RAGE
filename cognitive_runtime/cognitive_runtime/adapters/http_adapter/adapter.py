import json
import time
import urllib.error
import urllib.request
from typing import Any

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult

from .events import (
    create_http_request_completed_event,
    create_http_request_failed_event,
    create_http_request_started_event,
    create_http_validation_failed_event,
)
from .exceptions import HttpValidationError


class HttpAdapter(ActionAdapter):
    """
    Adapter for executing HTTP operations.
    Relies strictly on urllib.request to avoid external dependencies.
    """

    SUPPORTED_TYPES = {
        ActionType.HTTP_GET,
        ActionType.HTTP_POST,
    }

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self.SUPPORTED_TYPES

    def validate(self, action: Action) -> None:
        if action.type not in self.SUPPORTED_TYPES:
            raise HttpValidationError(f"Unsupported action type: {action.type}")

        if not action.target:
            raise HttpValidationError("Target URL is required.")

        if not (action.target.startswith("http://") or action.target.startswith("https://")):
            raise HttpValidationError("URL must start with http:// or https://.")

        params = action.parameters or {}
        
        if "headers" in params and not isinstance(params["headers"], dict):
            raise HttpValidationError("'headers' parameter must be a dictionary.")

        if "timeout" in params and not isinstance(params["timeout"], (int, float)):
            raise HttpValidationError("'timeout' parameter must be a number.")

    def execute(self, action: Action) -> ExecutionResult:
        start_time = time.perf_counter()

        try:
            self.validate(action)
        except HttpValidationError as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_http_validation_failed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    url=action.target,
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

        self._bus.publish(
            create_http_request_started_event(
                action_id=action.action_id,
                action_type=action.type.value,
                url=action.target,  # type: ignore[arg-type]
            )
        )

        try:
            output = self._dispatch(action)
            duration = (time.perf_counter() - start_time) * 1000
            
            # For urllib, HTTPError is raised for 4xx/5xx responses. 
            # We catch it in the except block, but if we get here, it's a 2xx.
            
            self._bus.publish(
                create_http_request_completed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    url=action.target,  # type: ignore[arg-type]
                    status_code=output["status_code"],
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
            
        except urllib.error.HTTPError as e:
            # 4xx or 5xx responses. 
            # A 404 is a valid HTTP response, we will treat HTTP error
            # statuses as execution success=True.
            
            duration = (time.perf_counter() - start_time) * 1000
            
            try:
                body_bytes = e.read()
                try:
                    body = body_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    body = body_bytes.hex()
            except Exception:
                body = ""
                
            output = {
                "status_code": e.code,
                "headers": dict(e.headers),
                "body": body,
                "content_type": e.headers.get("Content-Type", ""),
                "content_length": len(body_bytes) if 'body_bytes' in locals() else 0,
            }
            
            self._bus.publish(
                create_http_request_completed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    url=action.target,  # type: ignore[arg-type]
                    status_code=e.code,
                    duration_ms=duration,
                )
            )
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=True,  # The request completed successfully
                output=output,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._bus.publish(
                create_http_request_failed_event(
                    action_id=action.action_id,
                    action_type=action.type.value,
                    url=action.target,  # type: ignore[arg-type]
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

    def _dispatch(self, action: Action) -> dict[str, Any]:
        params = action.parameters or {}
        method = "GET" if action.type == ActionType.HTTP_GET else "POST"
        
        headers = params.get("headers", {})
        timeout = params.get("timeout", 10.0)
        
        data = None
        if method == "POST" and "body" in params:
            body = params["body"]
            if isinstance(body, dict):
                data = json.dumps(body).encode("utf-8")
                if "Content-Type" not in headers and "content-type" not in headers:
                    headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")
            else:
                data = str(body).encode("utf-8")

        # By default, urllib doesn't add a user-agent, which some servers block
        if "User-Agent" not in headers and "user-agent" not in headers:
            headers["User-Agent"] = "RAGE-Cognitive-Runtime/1.0"

        req = urllib.request.Request(
            url=action.target,  # type: ignore[arg-type]
            data=data,
            headers=headers,
            method=method,
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body_bytes = response.read()
            try:
                body_str = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_str = body_bytes.hex()  # hex string for binary
                
            return {
                "status_code": response.status,
                "headers": dict(response.headers),
                "body": body_str,
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": len(body_bytes),
            }
