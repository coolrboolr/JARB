import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from agent import Agent

logger = logging.getLogger(__name__)

_AGENT_SINGLETON: Optional[Agent] = None


def create_agent(
    *,
    llm_backend: Optional[str] = None,
    api_key: Optional[str] = None,
    tools_dir: Optional[str | Path] = None,
    flow_dir: Optional[str | Path] = None,
    log_dir: Optional[str | Path] = None,
    tool_generator=None,
    tool_library=None,
    dependency_manager=None,
    flow_library=None,
    load_env: bool = True,
) -> Agent:
    """Instantiate a new Agent with optional overrides."""

    if load_env:
        load_dotenv()

    backend = (llm_backend or os.getenv("JARB_LLM_BACKEND", "openai")).strip().lower()

    resolved_api_key = api_key
    if resolved_api_key is None and tool_generator is None:
        resolved_api_key = _load_api_key_for_backend(backend)

    agent = Agent(
        llm_backend=backend,
        api_key=resolved_api_key,
        tool_generator=tool_generator,
        tool_library=tool_library,
        dependency_manager=dependency_manager,
        log_dir=Path(log_dir) if log_dir else None,
        tools_dir=Path(tools_dir) if tools_dir else None,
        flow_library=flow_library,
        flow_dir=Path(flow_dir) if flow_dir else None,
    )
    logger.info("Initialized Agent with backend '%s'", backend)
    return agent


def get_shared_agent() -> Agent:
    """Return a cached Agent singleton backed by environment defaults."""

    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = create_agent()
    return _AGENT_SINGLETON


def _load_api_key_for_backend(backend: str) -> str:
    env_map = {
        "openai": "OPENAI_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = env_map.get(backend, "OPENAI_KEY")
    api_key = os.getenv(env_var)

    if not api_key:
        raise RuntimeError(
            f"Missing API key for backend '{backend}'. Set the {env_var} environment variable."
        )

    return api_key
