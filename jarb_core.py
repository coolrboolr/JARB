"""
jarb_core: Thin public facade around the Agent.

This module is the single import point used by:
- main.py (CLI smoke)
- api.py (Flask HTTP surface)
- tests/jarb_core/test_public_api.py

It owns an in-process Agent singleton which can be:
- lazily created from environment defaults, or
- explicitly replaced via `configure(...)`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agent import Agent
from agent_factory import create_agent, get_shared_agent as _factory_shared_agent

_AGENT: Optional[Agent] = None


def _get_agent() -> Agent:
    """
    Return the current Agent instance.

    If `configure()` has never been called, we fall back to the
    environment-driven singleton from agent_factory.get_shared_agent().
    """
    global _AGENT
    if _AGENT is None:
        _AGENT = _factory_shared_agent()
    return _AGENT


def configure(
    *,
    llm_backend: Optional[str] = None,
    api_key: Optional[str] = None,
    tools_dir: Optional[str | Path] = None,
    log_dir: Optional[str | Path] = None,
    flow_dir: Optional[str | Path] = None,
    load_env: bool = True,
    tool_generator=None,
    tool_library=None,
    dependency_manager=None,
    flow_library=None,
) -> Agent:
    """
    Create and install a fresh Agent singleton.

    Calling configure() again replaces the previous Agent with a new one.
    """
    global _AGENT

    _AGENT = create_agent(
        llm_backend=llm_backend,
        api_key=api_key,
        tools_dir=tools_dir,
        flow_dir=flow_dir,
        log_dir=log_dir,
        tool_generator=tool_generator,
        tool_library=tool_library,
        dependency_manager=dependency_manager,
        flow_library=flow_library,
        load_env=load_env,
    )
    return _AGENT


# ---------------------------------------------------------------------------
# Tool helpers (public API)
# ---------------------------------------------------------------------------

def create_tool(name: str, description: str) -> None:
    _get_agent().create_tool(name, description)


def list_tools() -> List[str]:
    return _get_agent().list_tools()


def describe_tool(name: str) -> Dict[str, Any]:
    return _get_agent().describe_tool(name)


def use_tool(name: str, **kwargs: Any) -> Any:
    return _get_agent().use_tool(name, **kwargs)


def get_tool_source(name: str) -> str:
    return _get_agent().get_tool_source(name)


def get_tool_signature(name: str):
    return _get_agent().get_tool_signature(name)


def get_tool_catalog() -> List[Dict[str, Any]]:
    return _get_agent().get_tool_catalog()


def get_tool_runs(name: str, limit: int = 20) -> List[Dict[str, Any]]:
    return _get_agent().get_tool_runs(name, limit=limit)


# ---------------------------------------------------------------------------
# Flow helpers (public API)
# ---------------------------------------------------------------------------

def create_flow(flow_spec: Dict[str, Any]) -> None:
    _get_agent().create_flow(flow_spec)


def list_flows() -> List[str]:
    return _get_agent().list_flows()


def describe_flow(flow_name: str) -> Dict[str, Any]:
    return _get_agent().describe_flow(flow_name)


def run_flow(flow_name: str, inputs: Optional[Dict[str, Any]] = None) -> Any:
    return _get_agent().run_flow(flow_name, inputs or {})


def get_flow_runs(flow_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    return _get_agent().get_flow_runs(flow_name, limit=limit)


__all__ = [
    "configure",
    "create_tool",
    "list_tools",
    "describe_tool",
    "use_tool",
    "get_tool_source",
    "get_tool_signature",
    "get_tool_catalog",
    "get_tool_runs",
    "create_flow",
    "list_flows",
    "describe_flow",
    "run_flow",
    "get_flow_runs",
]
