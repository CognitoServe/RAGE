import time

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.core.registry.interfaces import ServiceRegistry
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.executor.interfaces import ActionAdapter
from cognitive_runtime.executor.models import ExecutionResult

from .events import (
    create_plugin_execution_completed_event,
    create_plugin_execution_failed_event,
    create_plugin_execution_started_event,
    create_plugin_validation_failed_event,
)
from .exceptions import PluginAdapterError, PluginValidationError
from .interfaces import PluginRegistryInterface


class PluginAdapter(ActionAdapter):
    """
    Adapter for executing registered plugins.
    """

    SUPPORTED_TYPES = {
        ActionType.PLUGIN_CALL,
    }

    def __init__(self, event_bus: EventBus, registry: ServiceRegistry) -> None:
        self._bus = event_bus
        self._registry = registry

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self.SUPPORTED_TYPES

    def validate(self, action: Action) -> None:
        if action.type not in self.SUPPORTED_TYPES:
            raise PluginValidationError(f"Unsupported action type: {action.type}")

        if not action.target:
            raise PluginValidationError("Target (plugin name) is required.")

    def execute(self, action: Action) -> ExecutionResult:
        start_time = time.perf_counter()

        try:
            self.validate(action)
        except PluginValidationError as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_plugin_validation_failed_event(
                    action_id=action.action_id,
                    plugin_name=action.target,
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

        plugin_name = action.target
        params = action.parameters or {}

        # 1. Resolve PluginRegistry
        try:
            plugin_registry = self._registry.get(PluginRegistryInterface)
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"Failed to retrieve PluginRegistry from ServiceRegistry: {e}"
            self._bus.publish(
                create_plugin_execution_failed_event(
                    action_id=action.action_id,
                    plugin_name=plugin_name,
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

        # 2. Resolve specific plugin
        try:
            plugin = plugin_registry.get(plugin_name)
        except PluginAdapterError as e:
            duration = (time.perf_counter() - start_time) * 1000
            self._bus.publish(
                create_plugin_execution_failed_event(
                    action_id=action.action_id,
                    plugin_name=plugin_name,
                    reason=str(e),
                    duration_ms=duration,
                )
            )
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

        # 3. Invoke plugin
        self._bus.publish(
            create_plugin_execution_started_event(
                action_id=action.action_id,
                plugin_name=plugin.name(),
                parameters=params,
            )
        )

        try:
            result_data = plugin.execute(params)
            duration = (time.perf_counter() - start_time) * 1000

            self._bus.publish(
                create_plugin_execution_completed_event(
                    action_id=action.action_id,
                    plugin_name=plugin.name(),
                    plugin_version=plugin.version(),
                    duration_ms=duration,
                )
            )

            return ExecutionResult(
                action_id=action.action_id,
                action_type=action.type,
                success=True,
                output=result_data,
                duration_ms=duration,
                metadata={
                    "plugin_name": plugin.name(),
                    "plugin_version": plugin.version(),
                },
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"Plugin execution failed: {type(e).__name__}: {str(e)}"
            self._bus.publish(
                create_plugin_execution_failed_event(
                    action_id=action.action_id,
                    plugin_name=plugin.name(),
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
                metadata={
                    "plugin_name": plugin.name(),
                    "plugin_version": plugin.version(),
                },
            )
