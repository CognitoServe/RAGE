# HTTP Adapter — RFC-0015

## Overview

The `HttpAdapter` is the sole component in the RAGE cognitive runtime permitted to perform outbound network requests. It processes `HTTP_GET` and `HTTP_POST` actions, translating them into synchronous network calls and returning structured `ExecutionResult`s.

By isolating HTTP logic in this adapter, we ensure that planners, executors, and the rest of the runtime remain entirely decoupled from network protocols and error handling.

---

## Supported Operations

The adapter responds to the following `ActionType`s:

| ActionType | Description | Required Parameters |
|---|---|---|
| `HTTP_GET` | Perform an HTTP GET request | *None* |
| `HTTP_POST` | Perform an HTTP POST request | *None* (but usually includes `body`) |

*Note: All operations require a valid HTTP/HTTPS URL in the `target` field of the Action.*

### Optional Parameters

Both operations support the following optional fields in `parameters`:
- `headers` (dict): HTTP headers to include in the request. If no `User-Agent` is specified, `RAGE-Cognitive-Runtime/1.0` is used by default.
- `timeout` (float): Request timeout in seconds (default: 10.0s).

For `HTTP_POST`:
- `body` (str, dict, or bytes): The payload. If a dictionary is provided, it is automatically JSON-encoded, and `Content-Type: application/json` is added to the headers (if not already present).

---

## Execution Results

A successful HTTP request (including 4xx and 5xx error responses) returns an `ExecutionResult` with `success=True` and the following payload in `output`:
- `status_code` (int): e.g. 200, 404, 500
- `headers` (dict): The HTTP response headers.
- `body` (str): The response body. Binary data is hex-encoded.
- `content_type` (str): Extracted from headers.
- `content_length` (int): Number of bytes received.

Network errors (e.g., DNS failures, connection timeouts, SSL errors) are caught and returned as `ExecutionResult`s with `success=False` and the error described in the `error` field.

---

## Security & Constraints

1. **Protocols**: Only `http://` and `https://` are permitted.
2. **Minimalism**: No authentication frameworks, no cookie jars, and no connection pooling. 
3. **Stateless**: The adapter maintains no state across requests.
4. **No Retries**: The adapter executes a single request attempt. Retries are the responsibility of the scheduling/executor layer.
5. **Standard Library Only**: The adapter uses Python's built-in `urllib.request` to avoid taking on heavy external dependencies like `requests` or `httpx`.
