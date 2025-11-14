# SPEC4 – Stabilize the HTTP API surface

## Context
- `api.py` currently returns inconsistent JSON objects (sometimes only `{ "error": ... }`) and lacks a standard success/error envelope. External agents cannot rely on predictable responses.
- Routes reach directly into `agent.tool_library` and perform ad-hoc introspection rather than using the metadata helpers introduced in SPEC3.
- There are no automated tests for the Flask routes, so regressions slip through.
- External consumers (Codex, LangGraph) need a durable API contract with clear error semantics.

## Objectives
- Define a consistent JSON envelope for all responses (e.g., `{ "success": true/false, "data": ..., "error": {...} }`).
- Ensure every route uses `Agent` helper methods (`create_tool`, `use_tool`, `list_tools`, `describe_tool`).
- Add Flask integration tests covering both happy paths and error handling for all existing routes.
- Document the API (routes, payloads, sample curl commands) in `README.md` and mention any cross-origin allowances.

## Scope (In / Out)
- **In scope:** `api.py`, `README.md`, new tests under `tests/api/` plus any fixtures needed.
- **Out of scope:** Authentication, rate limiting, or adding new routes. Those can be later specs once the surface is stable.

## Required Changes
- **`api.py`**
  - Introduce helper functions:
    - `_success(data: object | None = None, status: int = 200)` returning `(jsonify({"success": True, "data": data}), status)`.
    - `_error(code: str, message: str, status: int)` returning `(jsonify({"success": False, "error": {"code": code, "message": message}}), status)`.
  - Wrap each route:
    - `POST /api/create_tool`: validate `name`/`description`; on success return `_success({"message": "Tool created"}, 201)`; on failure log exception and return `_error("CREATE_FAILED", str(e), 500)`.
    - `POST /api/use_tool`: validate payload; return `{"result": ...}` inside `data`; handle missing tool with `_error("NOT_FOUND", ...)` if `FileNotFoundError` raised.
    - `GET /api/list_tools`: return list via `_success({"tools": agent.list_tools()})`.
    - `GET /api/tool_parameters/<name>`: leverage `Agent.describe_tool` to return metadata; missing tool -> `_error("NOT_FOUND", ...)`.
  - Add `@app.errorhandler(Exception)` to convert uncaught exceptions into `_error("INTERNAL_ERROR", ...)` while logging stack traces.
  - Optional: add `@app.after_request` to set `Access-Control-Allow-Origin: *` to make the API easier to call from browser-based tooling (no new deps needed).

- **Tests (`tests/api/test_api_routes.py`)**
  - Use Flask’s `app.test_client()` along with a stub Agent to avoid hitting real ToolGenerator.
  - Sample tests:
    1. Missing `name`/`description` in `create_tool` returns 400 + error envelope.
    2. Happy-path `create_tool` returns 201 and records the call.
    3. `use_tool` returns data on success and `_error("NOT_FOUND"...)` when the Agent raises `FileNotFoundError`.
    4. `list_tools` returns expected tool names.
    5. `tool_parameters` returns metadata dict (mirroring `describe_tool`) or 404 for missing tool.
    6. Simulate an uncaught exception (stub agent raising) and assert the global handler responds with `INTERNAL_ERROR`.
  - Implement lightweight stub Agent class inside the test module; inject it by constructing the Flask app via a factory (create a `create_app(agent_override=None)` function in `api.py` to facilitate this).

- **`README.md`**
  - Add an "HTTP API Reference" section documenting each route, required payload, response envelope, and sample curl commands.
  - Mention CORS behavior if implemented.

## Implementation Notes and Constraints
- Keep dependencies unchanged—use base Flask only.
- Avoid duplicating logic: factor any shared validation into helper functions inside `api.py`.
- Tests should not modify real `tools/`; stub agents should operate in-memory.
- Preserve backwards compatibility where possible: existing clients receiving `data.result` should continue to work (document structure clearly).

## Tests & Verification
1. `python -m pytest tests/api/test_api_routes.py`.
2. Manual curl sequence against `python api.py` verifying success/error envelopes for each route.
3. (Optional) Browser fetch (or `curl -H "Origin: ..."`) to confirm CORS header is present if added.

## Future Work Hooks
- Once the HTTP surface is stable, future specs can layer authentication, rate limits, or OpenAPI docs without changing response contracts.
- SPEC5 will mirror these APIs in a Python package, so keep envelopes simple and easy to re-use in pure-Python functions.
