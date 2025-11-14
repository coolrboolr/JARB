# SPEC4 – Stabilize the HTTP API Surface

## Title & Context
The JARB backend now exposes multiple Flask routes (`/api/create_tool`, `/api/use_tool`, `/api/list_tools`, `/api/tool_parameters/<name>`, `/api/tools`) driven by the Agent abstractions introduced in SPEC1–SPEC3. Each route currently emits ad-hoc JSON structures (some return `{result: ...}`, others `{tools: ...}`, and errors often appear as bare `{"error": "..."}`), and there is no global error handler or shared response envelope. SPEC3 added `Agent.get_tool_catalog()` plus `GET /api/tools`, but this endpoint also returns a bare `{tools: [...]}` object. Meanwhile, backend unit tests exist for the llm adapter (`tests/unit/test_llm_api.py`, `tests/unit/test_tool_generator_llm_adapter.py`) and Agent catalog aggregation (`tests/unit/test_agent_catalog.py`), and SPEC3 introduced endpoint tests for `/api/tools` in `tests/unit/test_api_tools_endpoint.py`. With external consumers (future JS frontend, LangGraph, Codex) depending on consistent payloads, we need to stabilize the HTTP contract across **all** routes without touching the underlying LLM plumbing.

## Objectives
- Introduce a consistent JSON response envelope for every API route:
  - `{ "success": bool, "data": object | null, "error": { "code": str, "message": str } | null }`.
- Apply the envelope to `/api/create_tool`, `/api/use_tool`, `/api/list_tools`, `/api/tool_parameters/<name>`, and `/api/tools`.
- Retain existing Agent responsibilities (create/use/list/describe/get_tool_catalog) and have routes delegate to those methods without duplicating business logic.
- Update/expand Flask tests so that success and failure paths for **every** route assert the new envelope, including the `/api/tools` scenarios already covered in SPEC3.
- Prepare the surface for future consumers (e.g., browser UI) to rely on `/api/tools` and `/api/use_tool` without anticipating further contract changes.

## Scope
### In Scope
- `api.py` refactor to add response helpers, standard error codes, and optionally a global error handler.
- Flask route tests (ideally consolidated under `tests/api/`), including migration of the existing `/api/tools` tests.
- README documentation updates covering every HTTP route and the new envelope.

### Out of Scope
- Any changes to `Agent`, `ToolGenerator`, `LLMConfig`, or `llm_call` behavior.
- Adding new endpoints, authentication, rate limiting, or websocket support.
- Frontend implementation (reserved for a future spec once the API surface is stable).

## API Envelope & Route Behavior
### Helper Functions
- `_success(data: object | None = None, status: int = 200)` → returns `(jsonify({"success": True, "data": data, "error": None}), status)`.
- `_error(code: str, message: str, status: int)` → returns `(jsonify({"success": False, "data": None, "error": {"code": code, "message": message}}), status)`.
- Global error handler (`@app.errorhandler(Exception)`) should log the exception and respond with `_error("INTERNAL_ERROR", "Unexpected server error", 500)` unless the error is already an HTTPException.

### Route Contracts
| Route | Method | Behavior | Success `data` payload |
|-------|--------|----------|------------------------|
| `/api/create_tool` | POST | Validate `name` & `description`. Call `agent.create_tool`. | `{ "message": "Tool created successfully" }` |
| `/api/use_tool` | POST | Validate `tool_name` & `params` (dict). Call `agent.use_tool`. | `{ "result": <return value> }` |
| `/api/list_tools` | GET | Call `agent.list_tools`. | `{ "tools": [...] }` |
| `/api/tool_parameters/<name>` | GET | Call `agent.describe_tool`. | `{ "name": ..., "docstring": ..., "parameters": [...], "return_annotation": ... }` |
| `/api/tools` | GET | Call `agent.get_tool_catalog`. | `{ "tools": [...] }` |

### Error Handling
- Validation errors → `_error("BAD_REQUEST", "...", 400)`.
- Missing tool (e.g., `FileNotFoundError`) → `_error("NOT_FOUND", "Tool ... not found", 404)`.
- Agent or dependency errors during create/use → `_error("CREATE_FAILED" | "EXECUTION_FAILED", message, 500)`.
- Unexpected exceptions → `_error("INTERNAL_ERROR", "Unexpected server error", 500)` via global handler.

## CORS & Cross-Origin Considerations
- Since the frontend currently shares the origin during development, full CORS support is optional. SPEC4 should either:
  - Leave CORS off but document that the existing setup assumes same-origin, **or**
  - Add a minimal `@app.after_request` hook that sets `Access-Control-Allow-Origin: *` (and the related headers) without introducing new dependencies. Document whichever choice is made so future specs know the baseline.

## Testing Strategy
- Consolidate HTTP tests into `tests/api/test_api_routes.py` (or similar), using Flask’s test client.
- Either expose an app factory in `api.py` or continue patching `api.agent` to inject stubs; whichever approach is chosen must let tests cover all routes without hitting real ToolGenerator logic.
- Required test cases:
  1. `/api/create_tool`: missing fields (400), successful creation (200), backend exception (500).
  2. `/api/use_tool`: missing tool_name/params (400), tool not found (404), successful invocation (200), execution error (500).
  3. `/api/list_tools`: success (200) returning list, internal error (500).
  4. `/api/tool_parameters/<name>`: success (200), tool missing (404), internal error (500).
  5. `/api/tools`: success (200, using catalog data), failure (500). Update/migrate existing tests from `tests/unit/test_api_tools_endpoint.py` to assert the envelope.
  6. Global error handler path: simulate an exception to ensure `_error("INTERNAL_ERROR", ...)` response.

## README / API Documentation
- Add an “HTTP API Reference” section documenting: method, URL, request schema, response envelope (success + error examples) for each route **including `/api/tools`**.
- Clarify whether CORS headers are present.
- Include example `curl` commands that show the new envelope, e.g. `curl -X POST ... /api/use_tool` returning `{"success": true, "data": {"result": 3}, "error": null}`.

## Implementation Notes & Constraints
- No new dependencies beyond Flask and existing stdlib modules.
- Centralize envelope helpers in `api.py` to avoid copy/paste logic across routes.
- Keep Agent interactions untouched; routes should just call Agent methods and wrap results/errors.
- Tests should use stub Agents and avoid touching real files or requiring actual LLM keys.
- Communicate breaking changes (e.g., clients now read `data.result`) in README so downstream consumers can adapt.

## Verification Steps
1. Run `python -m pytest tests/api/test_api_routes.py` (and any other relevant suites) to ensure coverage of the new envelope.
2. Start the Flask app (`python api.py`) and manually `curl` each route to verify the documented responses.
3. (Optional) From a browser console, `fetch('/api/tools')` to confirm the envelope and any CORS headers.

## Future Work / Hooks
- With the HTTP surface stabilized, future specs (e.g., a revived “SPEC5 – Browser Catalog UI”) can safely build on `/api/tools` and `/api/use_tool` without worrying about response shape changes.
- Later iterations can explore authentication, rate limiting, OpenAPI docs, or richer metadata without breaking existing consumers.
