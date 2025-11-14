# SPEC5 – Expose JARB as an embeddable Python library

## Context
- Today, consumers either run `main.py` or call the Flask API. There is no canonical importable API for orchestrators (LangGraph, Codex) to embed.
- `agent.py` already encapsulates core behavior, but there is no lightweight module that instantiates a shared Agent, exposes helper functions, and allows reconfiguration for tests.
- We need a simple, synchronous Python interface ("tool factory") while keeping CLI/API code aligned with the same internals.

## Objectives
- Add a `jarb_core` package exposing top-level functions (`configure`, `create_tool`, `use_tool`, `list_tools`, `describe_tool`, `get_tool_callable`).
- Ensure the package uses a singleton Agent created via the same factory as CLI/API, with the ability to reconfigure (reset) for tests.
- Keep imports side-effect free (no Flask server start) and ensure module usage works without CLI/HTTP wrappers.
- Add tests verifying the package API reuses shared state, writes to the expected directories, and works with injected fake generators.
- Document the new public API in `README.md` with sample usage.
- Keep the public interface ready to expose upcoming **flow** capabilities (deterministic tool chains) without another refactor: once the FlowLibrary lands, `jarb_core` should simply forward the new Agent helpers the same way it already does for tools.

## Scope (In / Out)
- **In scope:** new package directory `jarb_core/`, updates to `agent.py` (exposing helper/factory), `main.py`, `api.py`, README, and tests under `tests/jarb_core/`.
- **Out of scope:** Publishing to PyPI, adding version metadata, or changing repository layout beyond the new package.

## Required Changes
- **`agent.py` / new helper module**
  - Extract the `_create_agent()` logic introduced earlier into a reusable function (e.g., `agent_factory.create_agent(llm_backend="openai", api_key=None, tools_dir="tools", tests_dir="tests", tool_generator=None, tool_library=None)`).
  - Ensure the factory loads `.env`, constructs `LLMConfig` (from SPEC2), and wires dependencies consistently.
  - Expose methods on `Agent` for `get_tool_callable(name)` (returning the actual callable) and ensure `describe_tool` remains available.

- **`jarb_core/__init__.py` (new)**
  - Implement module-level state: `_agent = None`.
  - Provide `configure(**kwargs)` that rebuilds `_agent` via the factory. Accept overrides for backend, api key, directories, and injected ToolGenerator/ToolLibrary for tests.
  - Implement `get_agent()` (private) that lazily creates `_agent` if `configure` hasn’t been called, using defaults.
  - Expose API functions delegating to the singleton: `create_tool`, `use_tool`, `list_tools`, `describe_tool`, `get_tool_callable`.
  - Leave clear extension points (module-level stubs or thin wrappers) so that once flows are implemented, adding `create_flow`, `run_flow`, etc. only requires delegating to the Agent—no rework of the singleton plumbing.
  - Document via docstrings that the module is not thread-safe for concurrent reconfiguration.

- **`main.py` & `api.py`**
  - Optionally switch to importing `jarb_core` functions instead of building their own Agents, keeping behavior consistent. (E.g., `from jarb_core import configure, create_tool` and call `configure()` at startup.)

- **`README.md`**
  - Add a "Library Usage" section with example code:
    ```python
    from jarb_core import configure, create_tool, use_tool, describe_tool
    configure(llm_backend="openai")
    create_tool("foo", "does bar")
    result = use_tool("foo", arg=1)
    ```
  - Mention how to point `configure` at alternative `tools/` directories for tests or multi-tenant setups.

- **Tests (`tests/jarb_core/test_public_api.py`)**
  - Use `tempfile.TemporaryDirectory` to isolate `tools/` and `tests/` directories by passing them to `configure`.
  - Inject a fake ToolGenerator (similar to SPEC1) via `configure(tool_generator=fake)`, ensuring `create_tool` writes deterministic code.
  - Verify `list_tools` reflects the persisted tool, `use_tool` executes it, `describe_tool` returns metadata, and repeated calls reuse the same Agent instance.
  - Add a test for `configure` resetting the singleton (call `configure`, create a tool, call `configure` again with new dirs, ensure tools list resets).

## Implementation Notes and Constraints
- Keep the public API synchronous and dependency-free beyond existing modules.
- Avoid circular imports: if `jarb_core` needs the factory, place the factory helper in its own module (e.g., `agent_factory.py`) that both API/CLI and `jarb_core` import.
- Ensure `configure` loads environment variables only when needed; allow callers to provide explicit keys for headless tests.
- Maintain compatibility with previous specs (metadata, LLM config, HTTP envelopes) **and** make sure flow-facing helpers can plug in when SPEC6 lands (e.g., by colocating tool + flow delegates, reusing the same Agent accessor, and documenting the expectation in README once flows exist).

## Tests & Verification
1. `python -m pytest tests/jarb_core/test_public_api.py` plus previously added suites.
2. Manual REPL smoke:
   ```python
   >>> from jarb_core import configure, list_tools
   >>> configure()
   >>> list_tools()
   ```
3. Run `python main.py` and `python api.py` to ensure they still function when backed by the shared module.

## Future Work Hooks
- Future specs can add higher-level helpers like `create_tool_from_spec(ToolSpec)` or LangGraph node wrappers on top of `jarb_core`.
- Once stable, consider packaging (`pyproject.toml`) and automated releases.
