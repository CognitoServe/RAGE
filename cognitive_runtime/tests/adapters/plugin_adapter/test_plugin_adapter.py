import threading
from typing import Any

import pytest

from cognitive_runtime.actions.models import Action, ActionType
from cognitive_runtime.adapters.plugin_adapter.adapter import PluginAdapter
from cognitive_runtime.adapters.plugin_adapter.exceptions import (
    PluginAlreadyRegisteredError,
    PluginNotFoundError,
)
from cognitive_runtime.adapters.plugin_adapter.interfaces import (
    Plugin,
    PluginRegistryInterface,
)
from cognitive_runtime.adapters.plugin_adapter.registry import DefaultPluginRegistry
from cognitive_runtime.core.registry.interfaces import ServiceRegistry
from cognitive_runtime.events.interfaces import EventBus
from cognitive_runtime.events.models import Event


class MockEventBus(EventBus):
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


class MockServiceRegistry(ServiceRegistry):
    def __init__(self) -> None:
        self.services: dict[type[Any], Any] = {}

    def register(self, interface_type: type[Any], implementation: Any) -> None:
        self.services[interface_type] = implementation

    def unregister(self, interface_type: type[Any]) -> None:
        self.services.pop(interface_type, None)

    def get(self, interface_type: type[Any]) -> Any:
        if interface_type not in self.services:
            raise Exception("Service not found")
        return self.services[interface_type]

    def contains(self, interface_type: type[Any]) -> bool:
        return interface_type in self.services

    def list_services(self) -> list[type[Any]]:
        return list(self.services.keys())


class ValidPlugin(Plugin):
    def name(self) -> str:
        return "ValidPlugin"

    def version(self) -> str:
        return "1.0.0"

    def execute(self, parameters: dict[str, Any]) -> Any:
        return {"result": parameters.get("value", 0) * 2}


class ThrowingPlugin(Plugin):
    def name(self) -> str:
        return "ThrowingPlugin"

    def version(self) -> str:
        return "0.1.0"

    def execute(self, _parameters: dict[str, Any]) -> Any:
        raise ValueError("Plugin encountered a fatal error")


@pytest.fixture
def bus() -> MockEventBus:
    return MockEventBus()


@pytest.fixture
def service_registry() -> MockServiceRegistry:
    return MockServiceRegistry()


@pytest.fixture
def plugin_registry() -> DefaultPluginRegistry:
    return DefaultPluginRegistry()


@pytest.fixture
def adapter(
    bus: MockEventBus,
    service_registry: MockServiceRegistry,
    plugin_registry: DefaultPluginRegistry,
) -> PluginAdapter:
    plugin_registry.register(ValidPlugin())
    plugin_registry.register(ThrowingPlugin())
    service_registry.register(PluginRegistryInterface, plugin_registry)
    return PluginAdapter(bus, service_registry)


def make_action(target: str, **params: Any) -> Action:
    return Action(
        plan_id="plan-1",
        step_id="step-1",
        type=ActionType.PLUGIN_CALL,
        target=target,
        parameters=params,
    )


class TestPluginRegistry:
    def test_register_and_get(self, plugin_registry: DefaultPluginRegistry) -> None:
        p = ValidPlugin()
        plugin_registry.register(p)
        assert plugin_registry.get("ValidPlugin") is p

    def test_duplicate_registration(
        self, plugin_registry: DefaultPluginRegistry
    ) -> None:
        p = ValidPlugin()
        plugin_registry.register(p)
        with pytest.raises(PluginAlreadyRegisteredError):
            plugin_registry.register(p)

    def test_not_found(self, plugin_registry: DefaultPluginRegistry) -> None:
        with pytest.raises(PluginNotFoundError):
            plugin_registry.get("UnknownPlugin")


class TestPluginAdapter:
    def test_supports(self, adapter: PluginAdapter) -> None:
        assert adapter.supports(ActionType.PLUGIN_CALL) is True
        assert adapter.supports(ActionType.FILE_READ) is False

    def test_validation_missing_target(self, adapter: PluginAdapter) -> None:
        action = make_action("")
        res = adapter.execute(action)
        assert res.success is False
        assert "Target (plugin name) is required" in res.error

    def test_execution_success(self, adapter: PluginAdapter, bus: MockEventBus) -> None:
        action = make_action("ValidPlugin", value=21)
        res = adapter.execute(action)
        
        assert res.success is True
        assert res.output == {"result": 42}
        assert res.error is None
        assert res.metadata["plugin_name"] == "ValidPlugin"
        assert res.metadata["plugin_version"] == "1.0.0"

        event_types = {e.event_type for e in bus.events}
        assert "PluginExecutionStarted" in event_types
        assert "PluginExecutionCompleted" in event_types

    def test_execution_plugin_exception(
        self, adapter: PluginAdapter, bus: MockEventBus
    ) -> None:
        action = make_action("ThrowingPlugin")
        res = adapter.execute(action)
        
        assert res.success is False
        assert res.output is None
        assert "ValueError: Plugin encountered a fatal error" in res.error
        assert res.metadata["plugin_name"] == "ThrowingPlugin"

        event_types = {e.event_type for e in bus.events}
        assert "PluginExecutionFailed" in event_types

    def test_execution_plugin_not_found(self, adapter: PluginAdapter) -> None:
        action = make_action("NonExistentPlugin")
        res = adapter.execute(action)
        
        assert res.success is False
        assert "Plugin 'NonExistentPlugin' not found" in res.error

    def test_service_registry_missing(self, bus: MockEventBus) -> None:
        # Create an adapter with a service registry that DOES NOT have PluginRegistry
        empty_reg = MockServiceRegistry()
        bad_adapter = PluginAdapter(bus, empty_reg)
        
        action = make_action("ValidPlugin")
        res = bad_adapter.execute(action)
        
        assert res.success is False
        assert "Failed to retrieve PluginRegistry" in res.error

class TestArchitectureConstraints:
    def test_no_planner_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "planner" not in source

    def test_no_goals_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "goals" not in source

    def test_no_memory_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "memory" not in source

    def test_no_process_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "process_adapter" not in source
        assert "subprocess" not in source

    def test_no_filesystem_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "filesystem" not in source

    def test_no_http_imports(self) -> None:
        import inspect

        import cognitive_runtime.adapters.plugin_adapter.adapter as mod
        source = inspect.getsource(mod)
        assert "adapters.http" not in source
