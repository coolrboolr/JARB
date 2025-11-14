# SPEC6 – Deterministic Flow Engine & Flow API

## Context
- JARB now has stable agents, metadata-aware ToolLibrary (SPEC3), consistent HTTP envelopes (SPEC4), and an embeddable `jarb_core` facade (SPEC5), but every invocation still targets a **single tool**.
- Users want to compose existing tools into deterministic, inspectable flows for multi-step jobs (e.g., pull data → transform → draft email) without regenerating code or wiring LangGraph.
- We have no persistence for flow specs, no way to replay / audit chained tool runs, and no UI or API surface to manage them.
- This spec introduces a minimal, file-backed FlowLibrary plus Agent/API/jarb_core entry points so future specs can add UIs and LLM planners on top.

## Objectives
- Support declarative flows defined as JSON/YAML dicts with ordered steps that call existing tools and reference prior inputs/results via `$inputs.*` and `$ctx.*` placeholders.
- Persist each flow as `<flows_dir>/<name>.json`, list them, fetch their specs, and log every run (per-step success/error) alongside existing tool logs for auditing.
- Extend `Agent` with flow lifecycle helpers: `create_flow`, `list_flows`, `describe_flow`, `run_flow`, `get_flow_runs`.
- Expose the same helpers through `jarb_core` so embedders can run flows without touching Flask.
- Add HTTP routes for flow CRUD/run/run-history that reuse the standard response envelope introduced in SPEC4.
- Provide regression tests for the FlowLibrary, Agent flow execution (happy + failure paths), and the new API endpoints.
- Document the schema plus example usage in README and keep CLI smoke paths for manual testing.

## Scope (In / Out)
- **In scope:** new `flow_library.py`, updates to `agent.py`, `jarb_core/__init__.py`, `api.py`, `main.py`, README, and new tests under `tests/flows/` and `tests/api/`.
- **Out of scope:** Visual flow editor/UI implementation (only outline needs), LLM-generated flow planning (reserved for follow-up), and deployment changes.

## Flow Schema
- Store each flow as JSON with keys: `name`, `description`, `inputs` (list of required external inputs), `steps` (array), and optional `output` expression.
- Step shape:
  ```jsonc
  {
    "id": "fetch",
    "tool": "fetch_data",
    "params": {"start_date": "$inputs.start_date", "end_date": "$inputs.end_date"},
    "save_as": "raw_data"
  }
  ```
- Placeholder rules:
  - `$inputs.foo` → parameter supplied to `run_flow`.
  - `$ctx.bar` → previous step output saved under `save_as` (or step `id` when `save_as` omitted).
  - Literals remain untouched.
- `output` can be a placeholder (preferred) or literal value.
- Document schema + example in README and include a sample `flows/example_report.json` checked into repo for smoke tests.

## Required Changes
1. **FlowLibrary (new `flow_library.py` or module inside `agent.py`):**
   - Manage a base directory (default `flows/`).
   - Methods: `list_flows()`, `get_flow(name)`, `save_flow(flow_spec)`, `delete_flow(name)` (optional but nice), returning native dicts.
   - Validate `name` uniqueness and ensure directories exist.

2. **Agent wiring:**
   - Accept `flow_dir: Path | str | None` in `Agent.__init__`; default to `flows/` under repo root, mirroring `tool_logs` parity.
   - Instantiate a `FlowLibrary` and expose helper methods that wrap it (`create_flow`, `list_flows`, `describe_flow`).
   - Implement `run_flow(flow_name, inputs)` executing steps sequentially:
     - Resolve parameters via `_resolve_flow_params` and `_resolve_flow_reference` helpers.
     - Call `use_tool` per step; on error, log failure and re-raise to stop the flow.
     - Support `save_as` (or fallback to `step.id`).
     - Resolve final `output` expression similarly.
   - Add `_log_flow_step` + `get_flow_runs` writing JSONL entries under `tool_logs/flow_<name>.jsonl` with `flow_run_id`, timestamps, params, results/errors, aligning with existing tool logging format.

3. **Validation & safety:**
   - Basic schema checks before saving/running (validate `steps` array, known tools, duplicates).
   - All placeholder lookups that miss should raise descriptive errors (e.g., `$ctx.missing`).
   - Ensure `run_flow` can accept optional `inputs` dict but enforces listed required keys.

4. **jarb_core integration:**
   - Add delegates `create_flow`, `list_flows`, `describe_flow`, `run_flow`, `get_flow_runs` that just forward to the singleton Agent configured in SPEC5.
   - Update docstrings so embedders know flows are available alongside tools.

5. **API routes (Flask):**
   - `POST /api/create_flow` – body `{ "flow": { ...spec... } }`. Returns `_success({"message": "Flow created"}, 201)`.
   - `POST /api/run_flow` – body `{ "flow_name": str, "inputs": { ... } }`. Returns `_success({"result": ...})` or `_error("NOT_FOUND", ...)`.
   - `GET /api/flows` – returns `_success({"flows": [...]})` (names + optional metadata).
   - `GET /api/flow/<name>` – returns `_success({"flow": spec})`.
   - `GET /api/flow_runs/<name>?limit=20` – returns `_success({"runs": [...]})` for auditing.
   - Reuse SPEC4 envelope helpers and logging; add tests for success + error states.

6. **CLI / Samples:**
   - Update `main.py` (or a small CLI helper) to list flows, optionally run one if `RUN_FLOW=<name>` is provided, and print the result.
   - Provide a sample deterministic flow file referencing existing tools (e.g., `fetch_dummy_data` + `summarize_text`).

7. **Testing:**
   - `tests/flows/test_flow_library.py`: CRUD roundtrip, schema validation, placeholder resolution edge cases.
   - `tests/flows/test_agent_flows.py`: use fake tools to assert multi-step execution, context passing, failure handling, and log generation (read JSONL to verify entries).
   - `tests/api/test_flow_routes.py`: Flask test client hitting new endpoints with stub Agent (success + failure).
   - Update any existing integration suites (e.g., `tests/jarb_core/test_public_api.py`) to cover new jarb_core flow delegates.

8. **Docs:**
   - README: add “Flows” section explaining schema, CLI/API usage, jarb_core snippet, and future roadmap (LLM planner + UI).
   - Mention flow storage location and how to clean up.

## Implementation Notes & Constraints
- Keep flows deterministic: no branching/looping yet. Steps run sequentially and stop on first failure.
- Storage: JSON only (avoid new deps). Accept YAML only after future spec.
- Logging should reuse `_json_safe` helper to keep params/results serializable.
- Flow execution reuses existing tool invocation path, so tool-level logging/tests stay valid.
- Keep FlowLibrary small enough to migrate later to SQLite if needed (design with interface boundaries).

## Tests & Verification
1. `python -m pytest tests/flows/ tests/api/test_flow_routes.py tests/jarb_core/test_public_api.py`.
2. Manual smoke: `python main.py --list-flows`, `curl -X POST /api/run_flow -d '{"flow_name":"example_report","inputs":{"start_date":"2025-10-01","end_date":"2025-10-31"}}'`.
3. Inspect `tool_logs/flow_example_report.jsonl` after a few runs to ensure per-step log entries.

## Future Work Hooks
- Layer in an `/api/plan_flow` endpoint that calls the LLM to propose flow specs using the same schema, requiring explicit approval before saving.
- Build a frontend “Flows” tab that lists flows, shows their steps/run history, and lets users trigger and edit them in-place.
- Explore caching/branching (`if`, `map`) once deterministic loops prove stable.
