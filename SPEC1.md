# SPEC1 – Consolidate JARB core and remove legacy jarb.py

## Context
- Two parallel implementations exist: `jarb.py` (JSON storage + bespoke Agent/ToolGenerator/ToolLibrary) and the newer modular versions in `agent.py`, `tool_library.py`, and `tool_generator.py`. They drift separately and confuse contributors.
- `agent.py` still wires in interactive `UserInterventionManager` prompts and assumes it is initialized with a simple backend string like "openai", even though `ToolGenerator` expects an API key/config.
- `api.py` and `main.py` instantiate their own Agents, so tool state diverges per process. There is no shared factory or stub-friendly injection point.
- Existing tests in `tests/` are sample scripts unrelated to the actual Agent/ToolLibrary flow. There is no regression test proving that generated tools persist and run.
- Assume Python 3.10+, local filesystem persistence under `/Users/coolrboolr/psf/JARB/tools`, and `.env`-provided LLM keys for OpenAI/Anthropic.

## Objectives
- Remove `jarb.py` so `agent.py` + `tool_generator.py` + `tool_library.py` form the single source of truth.
- Refactor `Agent` so it accepts injected ToolGenerator/ToolLibrary/DependencyManager instances and runs fully headless (no interactive prompts).
- Ensure `api.py` and `main.py` both construct their Agent via a shared helper that loads configuration from environment variables once.
- Provide lightweight integration tests that exercise `Agent.create_tool`, dependency handling, and ToolLibrary persistence without contacting a live LLM.
- Keep existing tool behavior (e.g., `subtract_numbers`) working through CLI and HTTP flows.

## Scope (In / Out)
- **In scope:** `jarb.py`, `agent.py`, `api.py`, `main.py`, `README.md`, new `tests/test_agent_integration.py`, and related helpers under `tools/` / `tests/` as needed for isolation.
- **Out of scope:** LLM adapter changes (`llm_api.py`, `tool_generator.py` internals), HTTP API surface redesign, or new persistence backends.

## Required Changes
- **`jarb.py`**
  - Delete the file entirely. Mention in `README.md` that the legacy monolith was removed in favor of the modular core.

- **`agent.py`**
  - Update `Agent.__init__` signature to accept `llm_backend: str = "openai"`, `api_key: str | None = None`, `tool_generator: ToolGenerator | None = None`, `tool_library: ToolLibrary | None = None`, and `dependency_manager: DependencyManager | None = None`.
  - Instantiate defaults lazily so tests can inject fakes.
  - Remove `UserInterventionManager` and any `input()` calls; `_handle_dependencies` should rely on `DependencyManager` plus logging.
  - Add helpers `list_tools()` and `describe_tool(name)` (returning a dict containing docstring + signature via `inspect`).
  - Ensure `DependencyManager` uses logger warnings instead of `print` and caches installed packages.

- **`api.py`**
  - Add a private `_create_agent()` that loads `.env`, reads `OPENAI_KEY`/`ANTHROPIC_API_KEY`, builds the `Agent`, and caches it (singleton).
  - Replace `agent = Agent("openai")` with `agent = _create_agent()` and switch route logic to call `Agent` helpers instead of reaching into `tool_library` directly.

- **`main.py`**
  - Reuse the same `_create_agent()` helper to ensure CLI behavior matches API behavior.
  - Provide a simple smoke script: list tools, optionally create a tool when `CREATE_TOOL_EXAMPLE=1`, then demonstrate calling an existing tool (e.g., `subtract_numbers`).

- **`README.md`**
  - Document the new single-source-of-truth architecture and explain how to configure API keys via `.env`.
  - Mention the removal of `jarb.py` and how to run the new integration test.

- **`tests/test_agent_integration.py` (new)**
  - Implement a `FakeToolGenerator` returning deterministic code (e.g., `def fake_tool(x): return x + 1`).
  - Write tests that: (1) create a tool via the Agent, (2) verify the `.py` file appears under a temporary `tools/` directory, (3) call `Agent.use_tool`, and (4) assert `Agent.list_tools()` reflects persisted tools.
  - Use temporary directories (`tempfile.TemporaryDirectory`) so the real repo tools stay untouched.

## Implementation Notes and Constraints
- Stay within existing dependencies; rely on stdlib (`tempfile`, `inspect`, `logging`).
- Preserve existing logging style (`logging.getLogger(__name__)`).
- Do not change `tool_generator.py` behavior yet; pass whatever config/keys `Agent` collects straight through.
- Keep storage layout under `tools/` and `tests/`; integration tests should isolate their own directories.
- Library code must remain non-interactive (no `input()` or `print()` beyond logging).

## Tests & Verification
1. `python -m pytest tests/test_agent_integration.py` (offline, uses fake generator).
2. `python main.py` to ensure listing/creating/using tools works without stack traces.
3. Run `python api.py` in one terminal and verify:
   - `curl -X GET http://127.0.0.1:5000/api/list_tools`
   - `curl -X POST http://127.0.0.1:5000/api/use_tool -H 'Content-Type: application/json' -d '{"tool_name":"subtract_numbers","params":{"a":5,"b":2}}'`

## Future Work Hooks
- SPEC2 will clean up `llm_api.py` and `ToolGenerator` so Agents receive structured backend configs instead of raw strings.
- Later specs will add richer ToolLibrary metadata and expose it over HTTP.
