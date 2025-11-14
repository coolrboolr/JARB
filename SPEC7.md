# SPEC7 – Close Outstanding Gaps from SPEC1–SPEC6

## Context
While SPEC1–SPEC6 delivered the unified Agent, HTTP envelope, jarb_core facade, and deterministic flows, a few acceptance criteria still remain incomplete or fragile. SPEC7 consolidates every known miss (mostly lingering SPEC3 metadata work plus API test ergonomics) so the project can declare the previous specs finished before moving on.

## Objectives
1. **Tool metadata parity (SPEC3 gap)**  
   - Promote `tool_library.ToolLibrary` to store structured metadata in a `ToolRecord` (`callable`, `path`, `signature`, `docstring`, `last_loaded`).  
   - Expose library-level helpers `get_tool_signature`, `get_tool_source`, and `describe_tool` that read from the cached metadata and refresh automatically when the on-disk file changes.  
   - Update Agent to rely on these helpers (and expose pass-throughs) so every surface—jarb_core, CLI, HTTP API—pulls metadata from the same source of truth instead of re-inspecting callables.  
   - Refresh README with a “Tool metadata & inspection” section showing sample output from `jarb_core.describe_tool` and `jarb_core.get_tool_signature`.

2. **Metadata regression tests (SPEC3 gap)**  
   - Add `tests/tool_library/test_metadata.py` covering: add/load/refresh of metadata, describe_tool error paths, get_tool_source accuracy, and signature/docstring integrity after file edits.  
   - Extend `tests/test_agent_integration.py` (or a new companion test) to assert `Agent.describe_tool`, `Agent.get_tool_signature`, and `Agent.get_tool_source` mirror the ToolLibrary data.

3. **HTTP regression suite stability (SPEC4 follow-up)**  
   - Ensure `tests/api/test_api_routes.py` (and any future API suites) can import the package without relying on external environment layout. Add/refresh `tests/conftest.py` to pin the repo root on `sys.path` and set safe default env vars (`OPENAI_KEY=test-key`, etc.).  
   - Document the testing workflow (env vars, commands, jarb_core configuration) so contributors can consistently run `pytest tests/api/test_api_routes.py` and the flow suites locally without mutating their global environment.

## Scope
- In scope: `tool_library.py`, `agent.py` metadata helpers, README updates, new/updated tests under `tests/tool_library/` and `tests/`.  
- Out of scope: new endpoints, ToolGenerator changes, or flow/HTTP contract tweaks beyond the stability tasks above.

## Deliverables
1. Refactored ToolLibrary + Agent metadata plumbing with doc updates and jarb_core passthroughs.
2. Metadata-focused unit tests and updated integration tests proving describe/signature/source behavior.
3. Stable pytest import setup documented and enforced so API + flow suites run via a single command.

## Verification
Run:  
```
python -m pytest tests/tool_library/test_metadata.py \
                 tests/test_agent_integration.py \
                 tests/jarb_core/test_public_api.py \
                 tests/flows \
                 tests/api/test_api_routes.py
```
All suites must pass without manual environment tweaks beyond `OPENAI_KEY`/`ANTHROPIC_API_KEY` defaults.
