# SPEC2 – Clean LLM adapter and configuration

## Context
- `tool_generator.ToolGenerator` accepts an `api_key` string but then calls `llm_api.llm_call`, which pulls `OPENAI_KEY` from the environment and ignores the provided value. The code path for Anthropic is similarly inconsistent and hard-coded.
- Provider-specific logic lives in multiple places (ToolGenerator, Agent, llm_api), making it difficult to add new backends such as Jan or to run offline tests.
- There are no unit tests around `llm_api.llm_call` or the way `ToolGenerator` interacts with it, so regressions go unnoticed until runtime.
- Goal: create a clean adapter layer with an explicit config object so ToolGenerator can request completions through a backend-agnostic interface.

## Objectives
- Centralize all provider details inside `llm_api.py`, using an explicit `LLMConfig` structure.
- Update `ToolGenerator` to accept an `LLMConfig` (or injected client) instead of ad-hoc api keys, and ensure every call to `llm_call` passes this config.
- Make `Agent` responsible for loading/constructing the config based on `llm_backend` and environment variables.
- Add offline unit tests covering `llm_api.llm_call` behavior for OpenAI and Anthropic, plus tests proving `ToolGenerator` uses the adapter correctly.
- Keep CLI (`main.py`) and HTTP API (`api.py`) behavior unchanged, just wired through the new config path.

## Scope (In / Out)
- **In scope:** `llm_api.py`, `tool_generator.py`, `agent.py` wiring, `main.py`, `api.py`, and new tests under `tests/unit/`.
- **Out of scope:** ToolLibrary metadata, HTTP response shapes, or adding new providers beyond OpenAI/Anthropic.

## Required Changes
- **`llm_api.py`**
  - Introduce `@dataclass LLMConfig` with fields such as `provider`, `api_key`, `model`, `temperature`, `max_tokens`, and optional `client_factory` for tests.
  - Add `load_llm_config(provider: str) -> LLMConfig` that reads keys/models from environment variables (`OPENAI_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_MODEL`, etc.) and raises a descriptive `RuntimeError` if missing.
  - Refactor `llm_call(prompt: str, config: LLMConfig, context: str | None = None)` to select the provider, instantiate the client (using `client_factory` when provided), and return the response text. Remove hard-coded placeholder keys.

- **`tool_generator.py`**
  - Update `__init__` to require `llm_config: LLMConfig` (or `llm_config: LLMConfig | None` plus default loader).
  - Store the config and pass it to all `llm_call` invocations (design/code/tests generations).
  - Accept an optional `llm_client` or `llm_call_func` for dependency injection in tests.
  - Adjust docstrings/logging to mention the config requirement.

- **`agent.py`**
  - When `tool_generator` is not provided, call `load_llm_config(llm_backend)` to build the config (unless `api_key` is explicitly provided; in that case, create a config manually).
  - Pass the config into `ToolGenerator`.
  - Update docstrings/commentary to explain how `llm_backend` maps to environment variables.

- **`main.py` & `api.py`**
  - Replace manual key handling with calls to `load_llm_config` (or to the shared `_create_agent` helper that already wraps it).
  - Fail fast with clear logging if required environment variables are missing.

- **Tests**
  - Create `tests/unit/test_llm_api.py` using `unittest` + `unittest.mock.patch` to stub `openai.chat.completions.create` and `anthropic.Anthropic`. Verify:
    1. `llm_call` passes prompt/context/model correctly.
    2. Missing environment variables cause `load_llm_config` to raise.
  - Create `tests/unit/test_tool_generator_llm_adapter.py` patching `llm_api.llm_call` to ensure `ToolGenerator.generate_design/code/tests` call it with the stored config.
  - Tests must run offline and not require actual API keys.

## Implementation Notes and Constraints
- Use stdlib `dataclasses` and `typing` only; do not add dependencies.
- Keep default models the same as current hard-coded values (`gpt-4o`, `claude-3-sonnet-20240229`) unless environment variables override them.
- Maintain existing logging behavior and file layouts (logs under `tool_logs/`).
- Raise descriptive errors when config is incomplete to aid CLI/API users.

## Tests & Verification
1. `python -m pytest tests/unit/test_llm_api.py tests/unit/test_tool_generator_llm_adapter.py`.
2. `python main.py` should still create/list/use tools (now failing fast when keys absent).
3. `python api.py` and run the smoke curl commands from SPEC1 to confirm runtime behavior unchanged.

## Future Work Hooks
- SPEC3 will rely on the stable Agent interface to expose metadata; ensure LLM config plumbing doesn’t leak into ToolLibrary concerns.
- Later SPECs can add new providers (Jan, MCP) by extending `LLMConfig` and `load_llm_config` without touching ToolGenerator internals again.
