J UST
A NOTHER
R EGULAR
B OT

A simple agentic flow that allows you to store functions for later use. 

Runs as a module for testing with `main.py` or through the HTTP + browser stack described below.

agent class can run create_tool to iterate through agentic flow

The flow:
1. Create a plan, iterate through it to optimize
2. Write code, and fix general errors until functional
3. Write unit tests and check to see if the code is running as expected
4. Save

Logs for each tool are available in tool_logs/tool_name.json - one file per tool created

## Architecture

`agent.py`, `tool_generator.py`, and `tool_library.py` now form the single source of truth for generating and storing tools. The legacy monolithic `jarb.py` implementation has been removed in favor of these modular components. Both the CLI (`main.py`), the embeddable Python API (`jarb_core`), and the Flask HTTP surface (`api.py`) share the same Agent instance created via `agent_factory.py`, so every entry point interacts with the exact same Tool/Flow libraries.

## Configuration

Create a `.env` file (or export env vars) with the LLM backend you want to use:

```
JARB_LLM_BACKEND=openai  # default
OPENAI_KEY=sk-...
# or export OPENAI_API_KEY for compatibility

# or, for Anthropic
JARB_LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=... 
# (ANTHROPIC_KEY is also accepted)
```

`agent_factory.py` loads `.env`, selects the correct key (`OPENAI_KEY`/`OPENAI_API_KEY` for OpenAI, `ANTHROPIC_API_KEY`/`ANTHROPIC_KEY` for Anthropic), and instantiates the singleton Agent for both CLI and HTTP entry points.

## Library usage (`jarb_core`)

Importers can embed the Agent directly without spinning up the CLI/API by using the `jarb_core` facade. It lazily builds (or reconfigures) the shared Agent via `agent_factory.create_agent`, so every helper stays in sync with the CLI/API behavior.

```python
from jarb_core import configure, create_tool, use_tool, list_tools, describe_tool

# Build the singleton Agent once. Pass overrides for alternative directories or fake generators in tests.
configure(llm_backend="openai")

create_tool("ticker_price", "Fetches delayed quotes and returns a dict")
print(list_tools())
print(describe_tool("ticker_price"))
print(use_tool("ticker_price", ticker="AAPL"))
```

- Call `configure(...)` again to reset the singleton (e.g., point at a temp `tools/` directory during tests).
- All tool helpers (`create_tool`, `use_tool`, `list_tools`, `describe_tool`, `get_tool_catalog`, `get_tool_runs`) and the new flow helpers (`create_flow`, `run_flow`, etc.) simply forward to the shared Agent.
- To skip environment loading (useful in unit tests), pass `load_env=False` and provide explicit settings or injected ToolGenerators.

## Tool metadata & inspection

`ToolLibrary` now stores structured metadata for every tool (callable, signature, docstring, on-disk path, last-loaded timestamp). `jarb_core.describe_tool("subtract_numbers")` returns:

```
{
  "name": "subtract_numbers",
  "docstring": "Subtract b from a.",
  "parameters": [
    {
      "name": "a",
      "kind": "POSITIONAL_OR_KEYWORD",
      "required": true,
      "default": null,
      "annotation": {"type": "int", "raw": "int"}
    },
    {
      "name": "b",
      "kind": "POSITIONAL_OR_KEYWORD",
      "required": true,
      "default": null,
      "annotation": {"type": "int", "raw": "int"}
    }
  ],
  "return_annotation": null
}
```

Additional helpers:
- `jarb_core.get_tool_source("subtract_numbers")` → returns the current file contents under `tools/subtract_numbers.py`.
- `jarb_core.list_tools()` → remains a simple list of names backed by the metadata cache.
- Metadata automatically refreshes whenever the on-disk `.py` file changes; the library checks `mtime` and reloads as needed.

## HTTP API Reference

All HTTP responses returned by `api.py` share the same envelope:

```
{
  "success": true | false,
  "data": { ... } | null,
  "error": null | { "code": "STRING", "message": "Human readable" }
}
```

The server also emits permissive CORS headers (`Access-Control-Allow-Origin: *`, etc.) so browser clients hosted elsewhere can call the API during development.

### Routes

| Method & Path | Description | Success `data` payload |
| ------------- | ----------- | ---------------------- |
| `POST /api/create_tool` | Creates a new tool with `name` and `description`. | `{ "message": "Tool created" }` |
| `POST /api/use_tool` | Executes a stored tool. Body fields: `tool_name` (string) and optional `params` object. | `{ "result": <return value> }` |
| `GET /api/list_tools` | Lists all stored tool names. | `{ "tools": [...] }` |
| `GET /api/tool_parameters/<tool_name>` | Returns docstring + parameters for a single tool. | `{ "name": "...", "parameters": [...], "docstring": "...", "return_annotation": ... }` |
| `GET /api/tools` | Returns the complete tool catalog (metadata for every tool). | `{ "tools": [...] }` |
| `GET /api/tool_runs/<tool_name>` | Returns recent run history for a tool (optional `?limit=20`). | `{ "runs": [...] }` |
| `POST /api/create_flow` | Persist a deterministic flow spec. Body `{ "flow": { ... } }`. | `{ "message": "Flow created" }` |
| `POST /api/run_flow` | Execute a stored flow with `{ "flow_name": str, "inputs": { ... } }`. | `{ "result": <flow output> }` |
| `GET /api/flows` | List stored flow names. | `{ "flows": [...] }` |
| `GET /api/flow/<name>` | Retrieve the full flow spec (steps, inputs, description). | `{ "flow": { ... } }` |
| `GET /api/flow_runs/<name>` | Flow run history (optional `?limit=20`). | `{ "runs": [...] }` |

Errors use the same envelope with `success: false`, `data: null`, and `error.code` such as `BAD_REQUEST`, `NOT_FOUND`, `LIST_FAILED`, `CATALOG_FAILED`, or `INTERNAL_ERROR`.

### Parameter metadata schema

Both `GET /api/tools` and `GET /api/tool_parameters/<tool_name>` describe each parameter with a stable schema:

```
{
  "name": "count",
  "kind": "POSITIONAL_OR_KEYWORD",
  "default": null,
  "required": true,
  "annotation": {
    "type": "int",      // one of: int, float, bool, str, json, any
    "raw": "int"        // stringified original annotation when available
  }
}
```

- `required` is `true` when the function signature has no default for that positional/keyword-only parameter.
- `annotation.type` is a lightweight, JSON-friendly label the frontend can use to choose input widgets. Complex hints such as `Optional[int]` collapse into their primary type, with fallbacks to `json` (for mappings/sequences) or `any` when no hint is available.
- `annotation.raw` simply preserves the original annotation string for debugging or richer clients.

### Tool run history

Each `/api/use_tool` invocation is appended to `tool_logs/<tool_name>.jsonl` and exposed through `GET /api/tool_runs/<tool_name>?limit=20` with entries like:

```
{
  "run_id": "0b345...",
  "tool_name": "subtract_numbers",
  "started_at": "2025-11-13T17:02:31.123Z",
  "finished_at": "2025-11-13T17:02:31.456Z",
  "duration_ms": 333,
  "status": "success",            // or "error"
  "error": null,                   // {"type":"ValueError","message":"..."} on failure
  "params": {"a": 5, "b": 2},
  "result_summary": "3"
}
```

Entries are returned most-recent-first. If a tool exists but hasn’t run yet, the API responds with an empty `runs` array.

### Example requests

Create a tool:

```bash
curl -X POST http://localhost:5000/api/create_tool \
  -H 'Content-Type: application/json' \
  -d '{"name":"subtract_numbers","description":"Subtract b from a."}'
```

Use a tool:

```bash
curl -X POST http://localhost:5000/api/use_tool \
  -H 'Content-Type: application/json' \
  -d '{"tool_name":"subtract_numbers","params":{"a":5,"b":2}}'
```

List/categorize tools:

```bash
curl http://localhost:5000/api/list_tools
curl http://localhost:5000/api/tool_parameters/subtract_numbers
curl http://localhost:5000/api/tools
```

## Deterministic flows

Flows let you chain existing tools without writing new Python. Each flow is a JSON document stored under `flows/<name>.json` with the following schema:

```jsonc
{
  "name": "example_math_flow",
  "description": "Sample chain that adds then subtracts",
  "inputs": ["a", "b"],
  "steps": [
    {
      "id": "sum",
      "tool": "add_numbers",
      "params": {"a": "$inputs.a", "b": "$inputs.b"},
      "save_as": "total"
    },
    {
      "id": "difference",
      "tool": "subtract_numbers",
      "params": {"a": "$ctx.total", "b": "$inputs.b"},
      "save_as": "delta"
    }
  ],
  "output": "$ctx.delta"
}
```

- `$inputs.foo` pulls from the inputs dict supplied to `run_flow`.
- `$ctx.alias` references the result stored by a prior step (`save_as` defaults to the `id`).
- Literal strings stay untouched, so you can mix constants with references.

The repo ships with `flows/example_math_flow.json`; point `RUN_FLOW=example_math_flow` when running `python main.py` (optionally pass `RUN_FLOW_INPUTS='{"a":5,"b":2}'`) to exercise it.

### Running flows via jarb_core

```python
from jarb_core import configure, run_flow, list_flows

configure()
print(list_flows())
print(run_flow("example_math_flow", {"a": 5, "b": 2}))
```

### Running flows via HTTP

```bash
curl -X POST http://localhost:5000/api/create_flow \
  -H 'Content-Type: application/json' \
  -d '{"flow": {"name":"double_subtract", "inputs":["value"], "steps":[...]}}'

curl -X POST http://localhost:5000/api/run_flow \
  -H 'Content-Type: application/json' \
  -d '{"flow_name":"example_math_flow","inputs":{"a":5,"b":2}}'
```

Every step invocation is appended to `tool_logs/flow_<name>.jsonl` with timestamps, params, result summaries, and error metadata. Query them via `GET /api/flow_runs/<name>` or `jarb_core.get_flow_runs("name")` for auditing.

## Browser UI

A lightweight Node server in `node_fe/` now serves a static browser UI that calls the Flask API directly (CORS is already enabled on the backend).

1. Start the backend (default port 5000):

   ```bash
   python api.py
   ```

2. In a separate terminal start the frontend server (default port 3000):

   ```bash
   cd node_fe
   # optional: override where API requests are sent
   # JARB_API_BASE=https://staging.example.com node index.js
   node index.js
   ```

3. Visit `http://localhost:3000` in a browser. The UI will:

   - Load the tool catalog via `GET /api/tools` and present an always-refreshable list of tools.
   - Show per-tool metadata (docstring, parameter list, return annotation) along with generated input fields and type badges.
   - Call `POST /api/use_tool` with the typed parameters, disabling the form while the request is in flight and displaying the `{success,data,error}` envelope outcome.
   - Surface backend failures (e.g., `NOT_FOUND`, `USE_FAILED`, `INTERNAL_ERROR`) with prominent banners so the user can adjust parameters or retry the catalog fetch.
   - Highlight required vs optional parameters, render booleans as checkboxes, numbers as numeric fields, and JSON as textareas with client-side validation before hitting the backend.
   - Display the 20 most recent runs for the selected tool (status, duration, params, result summary) using `GET /api/tool_runs/<tool_name>`.

`JARB_API_BASE` controls which backend host the browser targets; the same variable is exposed in the UI so switching between local and remote agents is a single env change.

### Frontend smoke test

To confirm the backend exposes the expected envelope before opening a browser, run the Node smoke test (backend must already be running):

```bash
node node_fe/test/smoke.js          # optionally set JARB_API_BASE to override the target host
```

The script performs `GET /api/tools`, asserts the `{success,data,error}` structure, and prints how many tools were returned.

## Testing

Run the flow/jarb_core/API suites:

```
python -m pytest tests/tool_library/test_metadata.py \
                 tests/test_agent_integration.py \
                 tests/jarb_core/test_public_api.py \
                 tests/flows \
                 tests/api/test_api_routes.py
```

LLM adapter + catalog unit tests still live under `tests/unit/`:

```
python -m pytest tests/unit/test_agent_catalog.py tests/unit/test_llm_api.py tests/unit/test_tool_generator_llm_adapter.py
```

The original integration test remains available:

```
python -m pytest tests/test_agent_integration.py
```

All pytest runs share a `tests/conftest.py` helper that automatically adds the repo root to `sys.path`, so the CLI/API modules import consistently without extra setup. Provide dummy keys via `OPENAI_KEY`/`ANTHROPIC_API_KEY` when running the suites locally; the tests never call the real LLM endpoints.
