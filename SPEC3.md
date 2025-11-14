# SPEC3 – Harden ToolLibrary with metadata and introspection

## Context
- `tool_library.ToolLibrary` currently stores only callables in-memory and writes raw `.py` files to `tools/`. There is no structured metadata for signatures, docstrings, or source inspection.
- `api.py` and other consumers perform ad-hoc introspection, which will break once we add remote registries or multi-process orchestration.
- Future integration with LangGraph/MCP requires a stable way to describe tools (name, parameters, documentation, source) without re-importing modules manually.

## Objectives
- Extend `ToolLibrary` to maintain metadata (`inspect.Signature`, docstring, source path) for every tool.
- Provide public methods `get_tool_signature`, `get_tool_source`, and `describe_tool` returning predictable data.
- Ensure metadata stays in sync with on-disk files and that `Agent` exposes helper methods based on this metadata.
- Add unit tests covering metadata loading, cache refresh, and error handling.

## Scope (In / Out)
- **In scope:** `tool_library.py`, `agent.py` helper methods, documentation updates, and new tests under `tests/tool_library/` plus updates to existing integration tests.
- **Out of scope:** Changing storage format (still `tools/` files), HTTP response redesign (SPEC4), or new persistence layers like SQLite.

## Required Changes
- **`tool_library.py`**
  - Introduce a `@dataclass ToolRecord` storing `callable`, `path`, `signature`, `docstring`, and `last_loaded` timestamp if useful.
  - Replace `self.tools: Dict[str, Callable]` with `Dict[str, ToolRecord]`, but keep `get_tool`/`list_tools` return values backwards compatible (return the callable list).
  - On `add_tool`, after saving the `.py` file, populate a `ToolRecord` using `inspect.signature` and `inspect.getdoc`. Store the absolute file path.
  - Implement:
    - `get_tool_signature(name) -> inspect.Signature` (raise `KeyError` if missing).
    - `get_tool_source(name) -> str` (read from `tools/<name>.py`, raising `FileNotFoundError` if absent).
    - `describe_tool(name) -> dict` returning `{"name": name, "docstring": doc, "parameters": [{"name": ..., "default": ...}], "path": path}`.
  - Update `load_tool(s)` to rebuild `ToolRecord`s when files change, ensuring metadata stays fresh.
  - Ensure `remove_tool` deletes both file and record; log appropriately.

- **`agent.py`**
  - Update `list_tools()` to rely on the library (if not already) and add `describe_tool(name)` returning the dict from the ToolLibrary.
  - Provide `get_tool_signature`/`get_tool_source` proxies if needed by API routes/tests.
  - Adjust any other code paths (API/Main) to use these helpers rather than manual inspect logic.

- **Tests**
  - Add `tests/tool_library/test_metadata.py` covering:
    1. Adding a tool populates metadata and `get_tool_signature` returns expected parameters.
    2. Editing the underlying file (simulate by rewriting `tools/<name>.py`) and calling `load_tool` refreshes metadata.
    3. `describe_tool` raises/returns error objects when the tool is missing.
  - Update `tests/test_agent_integration.py` to assert `Agent.describe_tool(fake_tool)` returns the docstring/signature expected from the fake generator.

- **`README.md`**
  - Add a “Tool metadata & inspection” section showing how to call `Agent.describe_tool` with example output.

## Implementation Notes and Constraints
- Use stdlib only (`dataclasses`, `inspect`, `pathlib`).
- Metadata methods should raise clear exceptions (e.g., `KeyError` for missing tool) rather than returning partial data; document this behavior.
- Avoid re-import storms: reuse the existing `types.ModuleType` execution path, but rebuild metadata each time the tool is (re)loaded.
- Keep logging at INFO level when tools are loaded/saved; extra debug logs optional but minimal.

## Tests & Verification
1. `python -m pytest tests/test_agent_integration.py tests/tool_library/test_metadata.py`.
2. Manual smoke: `python - <<'PY' ...` to import `Agent` and print `agent.describe_tool("subtract_numbers")`.
3. `python api.py` and `GET /api/tool_parameters/<tool>` should still work, now powered by metadata helpers.

## Future Work Hooks
- SPEC4 will surface this metadata via the HTTP API’s JSON responses.
- Future specs may add alternative registries (SQLite, remote) but can reuse `ToolRecord` as the abstraction boundary.
