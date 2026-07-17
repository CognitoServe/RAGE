# Process Adapter — RFC-0017

## Overview

The `ProcessAdapter` executes operating system processes. It strictly limits process execution to avoid security vulnerabilities by enforcing a `shell=False` execution strategy, meaning raw command strings are never executed. Only explicitly defined executables with argument lists are supported.

## Security Constraints

1. **No `shell=True`**: It is impossible to use this adapter to execute raw shell expressions (e.g. `cat file | grep word > output`). By denying shell interpolation, RAGE prevents command injection attacks.
2. **Stateless**: The adapter does not maintain background daemons or process trees. It synchronously blocks for `PROCESS_START` up to the timeout. `PROCESS_STOP` is implemented by directly terminating the provided Process ID (PID).
3. **No Privilege Escalation**: The adapter does not elevate its own permissions. It inherits the permissions of the parent RAGE instance.

## Why is process execution isolated?

The Executor orchestrates execution. The Executor does not know *how* to run processes, talk to HTTP servers, or move files. If the Executor directly ran `subprocess`, it would violate the Single Responsibility Principle, and RAGE would lose the ability to intercept, log, and sandbox operations transparently. The Process Adapter solves this by providing a unified, secure boundary.

## Payloads

### `PROCESS_START`
- **target**: Path to the executable (e.g., `/bin/ls` or `python`).
- **parameters.args**: List of string arguments (e.g., `["-l", "/tmp"]`).
- **parameters.cwd**: Working directory string.
- **parameters.env**: Dictionary of environment variables.
- **parameters.timeout**: Timeout in seconds (default: 30.0).

### `PROCESS_STOP`
- **target**: Process ID (PID) as a string.
