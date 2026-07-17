# Plugin Adapter — RFC-0018

## Overview

The `PluginAdapter` is the sole execution bridge for invoking custom Python plugins within RAGE. It provides an opaque layer over internal extensions, meaning the rest of the cognitive architecture can treat plugin invocations identically to HTTP requests or filesystem operations.

## Architecture

Plugins are not executed directly by the Executor or Planner. Instead:
1. All plugins must implement the `Plugin` interface.
2. Plugins are registered by their string name in the `PluginRegistryInterface`.
3. The `PluginRegistryInterface` implementation (e.g. `DefaultPluginRegistry`) is registered in the core `ServiceRegistry`.
4. When the `PluginAdapter` receives a `PLUGIN_CALL` Action, it resolves the `PluginRegistryInterface` from the `ServiceRegistry`, fetches the requested plugin by name, and executes it.

This indirect resolution guarantees that RAGE can swap, mock, or hot-reload plugin logic internally without modifying the core Executor loop.

## Payloads

### `PLUGIN_CALL`
- **target**: The string name of the plugin (e.g., `"MyCalculatorPlugin"`).
- **parameters**: A dictionary of arbitrary parameters that will be passed directly to the plugin's `execute(parameters)` method.
