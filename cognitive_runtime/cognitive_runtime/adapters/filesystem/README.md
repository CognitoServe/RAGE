# Filesystem Adapter — RFC-0014

## Overview

The `FilesystemAdapter` is the only module in the RAGE cognitive runtime permitted to interact with the local filesystem. It executes filesystem actions received from the Executor by translating them into deterministic OS operations using `pathlib` and `shutil`.

---

## Why filesystem logic exists only here

By isolating filesystem operations:
- The Planner can plan file changes without knowing OS details.
- The Executor can orchestrate work without importing `os` or `shutil`.
- Testing other components doesn't require mocking the filesystem.
- Security constraints (e.g., path traversal checks) can be applied in one place.

## Supported Operations

The adapter responds to the following `ActionType`s:

| ActionType | Description | Required Parameters |
|---|---|---|
| `FILE_READ` | Read utf-8 text from a file | *None* |
| `FILE_WRITE` | Write utf-8 text to a file | `content` (str) |
| `FILE_MOVE` | Move or rename a file | `destination` (str) |
| `FILE_COPY` | Copy a file | `destination` (str) |
| `FILE_DELETE` | Delete a file | *None* |
| `DIRECTORY_CREATE` | Create a directory (and parents) | *None* |
| `DIRECTORY_DELETE` | Recursively delete a directory | *None* |

*Note: All operations require the `target` field on the Action to specify the primary path.*

---

## Security & Constraints

1. **Strict Types**: The adapter explicitly rejects directory operations on files (e.g., trying to read a directory as text) and file operations on directories (e.g., trying to delete a directory with `FILE_DELETE`).
2. **No Subprocesses**: The adapter never spawns shells (`os.system`, `subprocess`). It relies purely on Python's standard filesystem libraries.
3. **No Retries or Scheduling**: The adapter executes synchronously when called. If it fails, it returns a failed `ExecutionResult`. It is up to the Executor and Queue to handle retries.
4. **Stateless**: The adapter maintains no mutable state and is thread-safe.

---

## Failure Handling

The adapter never raises filesystem exceptions (`FileNotFoundError`, `PermissionError`, etc.) to the caller. 

Instead, it:
1. Catches the exception.
2. Publishes a `FilesystemOperationFailed` event (or `FilesystemValidationFailed` if the parameters were invalid).
3. Returns an `ExecutionResult` with `success=False` and `error` set to the exception message.

This ensures the orchestration layer never crashes due to bad file paths or missing permissions.
