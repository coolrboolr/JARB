import importlib.metadata
import json
import logging
import subprocess
import sys
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from llm_api import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OPENAI_MODEL,
    LLMConfig,
    load_llm_config,
)
from flow_library import FlowLibrary
from tool_generator import ToolGenerator
from tool_library import ToolLibrary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self,
        llm_backend: str = "openai",
        api_key: Optional[str] = None,
        tool_generator: Optional[ToolGenerator] = None,
        tool_library: Optional[ToolLibrary] = None,
        dependency_manager: Optional["DependencyManager"] = None,
        log_dir: Optional[Path] = None,
        tools_dir: Optional[Path] = None,
        flow_library: Optional[FlowLibrary] = None,
        flow_dir: Optional[Path] = None,
    ):
        self.llm_backend = llm_backend
        self.api_key = api_key
        self.tool_generator = tool_generator or self._build_tool_generator(api_key)
        self.tools_dir = Path(tools_dir) if tools_dir else Path("tools")
        self.tool_library = tool_library or ToolLibrary(str(self.tools_dir))
        self.dependency_manager = dependency_manager or DependencyManager()
        self.log_dir = Path(log_dir or "tool_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.flow_dir = Path(flow_dir) if flow_dir else Path("flows")
        self.flow_library = flow_library or FlowLibrary(self.flow_dir)

    def create_tool(self, name: str, description: str) -> None:
        code = self.tool_generator.create_tool(name, description)
        logger.info(f"Generated code for {name}:\n{code}")
        self._handle_dependencies(code)

        module = types.ModuleType(name)
        exec(code, module.__dict__)

        function = getattr(module, name, None)
        if not callable(function):
            function = self._find_first_callable(module)

        if function:
            self.tool_library.add_tool(name, function, code)
        else:
            logger.error(f"No function found in the generated code for {name}.")

    
    def get_tool_callable(self, tool_name: str):
        tool = self.tool_library.get_tool(tool_name)
        if not tool:
            raise FileNotFoundError(f"The tool {tool_name} does not exist or could not be loaded.")
        return tool

    def use_tool(self, tool_name: str, **kwargs):
        tool = self.get_tool_callable(tool_name)
        
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc)
        status = "success"
        error_info = None
        result = None

        try:
            result = tool(**kwargs)
            return result
        except Exception as exc:
            status = "error"
            error_info = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            finished_at = datetime.now(timezone.utc)
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            self._log_tool_run(
                tool_name=tool_name,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                status=status,
                error=error_info,
                params=kwargs,
                result=result,
            )

    def list_tools(self) -> List[str]:
        return self.tool_library.list_tools()

    def get_tool_signature(self, tool_name: str):
        return self.tool_library.get_tool_signature(tool_name)

    def get_tool_source(self, tool_name: str) -> str:
        return self.tool_library.get_tool_source(tool_name)

    def describe_tool(self, tool_name: str) -> Dict[str, Any]:
        return self.tool_library.describe_tool(tool_name)

    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        """Return metadata for all available tools without raising on individual failures."""
        catalog: List[Dict[str, Any]] = []
        for tool_name in self.list_tools():
            try:
                description = self.describe_tool(tool_name)
            except Exception as exc:  # pragma: no cover - defensive path
                logger.warning("Skipping tool '%s' while building catalog: %s", tool_name, exc)
                continue

            catalog.append({
                "name": description.get("name", tool_name),
                "docstring": description.get("docstring"),
                "parameters": description.get("parameters", []),
                "return_annotation": description.get("return_annotation"),
            })

        return catalog

    def get_tool_runs(self, tool_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.get_tool_callable(tool_name)

        limit = limit if isinstance(limit, int) and limit > 0 else 20

        log_file = self._log_file_for(tool_name)
        if not log_file.exists():
            return []

        try:
            with log_file.open("r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except FileNotFoundError:
            return []

        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed run log entry for tool '%s'", tool_name)
                continue
            entries.append(data)

        if not entries:
            return []

        sliced = entries[-limit:]
        return list(reversed(sliced))


    def _log_tool_run(
        self,
        *,
        tool_name: str,
        run_id: str,
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        status: str,
        error: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        result: Any,
    ) -> None:
        safe_params = self._json_safe(params)
        result_summary = self._summarize_result(result)
        entry = {
            "run_id": run_id,
            "tool_name": tool_name,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "params": safe_params,
            "result_summary": result_summary,
        }

        log_file = self._log_file_for(tool_name)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _log_file_for(self, tool_name: str) -> Path:
        safe_name = tool_name.replace("/", "_")
        return self.log_dir / f"{safe_name}.jsonl"

    @staticmethod
    def _summarize_result(result: Any) -> Optional[str]:
        if result is None:
            return None
        summary = repr(result)
        if len(summary) > 200:
            return summary[:197] + "..."
        return summary

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(key): self._json_safe(val) for key, val in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        return repr(value)

    def _handle_dependencies(self, code: str) -> None:
        # Extract import statements from the code
        import_lines = [line for line in code.split('\n') if line.startswith('import ') or line.startswith('from ')]
        for line in import_lines:
            parts = line.split()
            if parts[0] == 'import':
                package_name = parts[1].split('.')[0]
            elif parts[0] == 'from':
                package_name = parts[1].split('.')[0]
            self.dependency_manager.install_package(package_name)

    def _build_tool_generator(self, api_key: Optional[str]) -> ToolGenerator:
        config = self._create_llm_config(api_key)
        return ToolGenerator(config)

    def _create_llm_config(self, api_key: Optional[str]) -> LLMConfig:
        backend = self.llm_backend.strip().lower()

        if api_key:
            return LLMConfig(
                provider=backend,
                api_key=api_key,
                model=self._default_model_for_backend(backend),
            )

        return load_llm_config(backend)

    @staticmethod
    def _default_model_for_backend(backend: str) -> str:
        normalized = backend.strip().lower()
        if normalized == "anthropic":
            return DEFAULT_ANTHROPIC_MODEL
        if normalized == "openai":
            return DEFAULT_OPENAI_MODEL
        raise ValueError(f"Unsupported LLM backend '{backend}'.")

    @staticmethod
    def _find_first_callable(module: types.ModuleType):
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.lower().startswith("test"):
                return attr
        return None

    # Flow functionality -------------------------------------------------

    def create_flow(self, spec: Dict[str, Any]) -> None:
        validated = self._validate_flow_spec(spec)
        self.flow_library.save_flow(validated)

    def list_flows(self) -> List[str]:
        return self.flow_library.list_flows()

    def describe_flow(self, flow_name: str) -> Dict[str, Any]:
        flow = self.flow_library.get_flow(flow_name)
        if not flow:
            raise FileNotFoundError(f"The flow {flow_name} does not exist or could not be loaded.")
        return flow

    def run_flow(self, flow_name: str, inputs: Optional[Dict[str, Any]] = None) -> Any:
        flow = self.flow_library.get_flow(flow_name)
        if not flow:
            raise FileNotFoundError(f"The flow {flow_name} does not exist or could not be loaded.")

        inputs = inputs or {}
        if not isinstance(inputs, dict):
            raise ValueError("Flow inputs must be provided as an object/dict.")

        required_inputs = flow.get("inputs") or []
        missing = [key for key in required_inputs if key not in inputs]
        if missing:
            raise ValueError(f"Missing required flow inputs: {', '.join(sorted(missing))}")

        steps = flow.get("steps") or []
        if not steps:
            raise ValueError(f"Flow '{flow_name}' has no steps to execute.")

        ctx: Dict[str, Any] = {}
        last_result: Any = None
        flow_run_id = uuid.uuid4().hex

        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Flow '{flow_name}' has an invalid step at index {index}.")

            step_id = step.get("id") or f"step_{index + 1}"
            tool_name = step.get("tool")
            if not tool_name:
                raise ValueError(f"Flow '{flow_name}' step '{step_id}' is missing a tool name.")

            raw_params = step.get("params") or {}
            if not isinstance(raw_params, dict):
                raise ValueError(f"Flow '{flow_name}' step '{step_id}' params must be an object.")

            params = self._resolve_flow_params(raw_params, inputs, ctx)

            try:
                result = self.use_tool(tool_name, **params)
                status = "success"
                error = None
            except Exception as exc:  # pragma: no cover - re-raised after logging
                status = "error"
                result = None
                error = {"type": type(exc).__name__, "message": str(exc)}
                self._log_flow_step(
                    flow_name=flow_name,
                    flow_run_id=flow_run_id,
                    step_id=step_id,
                    tool_name=tool_name,
                    status=status,
                    params=params,
                    result=result,
                    error=error,
                )
                raise

            alias = step.get("save_as") or step_id
            ctx[alias] = result
            last_result = result

            self._log_flow_step(
                flow_name=flow_name,
                flow_run_id=flow_run_id,
                step_id=step_id,
                tool_name=tool_name,
                status=status,
                params=params,
                result=result,
                error=None,
            )

        output_expr = flow.get("output")
        if isinstance(output_expr, str) and output_expr.startswith("$"):
            return self._resolve_flow_reference(output_expr, inputs, ctx)
        if "output" in flow:
            return output_expr
        return last_result

    def get_flow_runs(self, flow_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.flow_library.get_flow(flow_name):
            raise FileNotFoundError(f"The flow {flow_name} does not exist or could not be loaded.")

        limit = limit if isinstance(limit, int) and limit > 0 else 20
        log_file = self._flow_log_file_for(flow_name)
        if not log_file.exists():
            return []

        with log_file.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()

        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed flow log entry for flow '%s'", flow_name)
                continue
            entries.append(data)

        if not entries:
            return []

        sliced = entries[-limit:]
        return list(reversed(sliced))

    def _validate_flow_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(spec, dict):
            raise ValueError("Flow spec must be a dictionary.")

        name = spec.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("Flow spec must include a string 'name'.")

        description = spec.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError("Flow description must be a string when provided.")

        inputs = spec.get("inputs")
        if inputs is None:
            spec["inputs"] = []
        elif not isinstance(inputs, list) or not all(isinstance(item, str) for item in inputs):
            raise ValueError("Flow 'inputs' must be a list of strings.")

        steps = spec.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Flow spec must include a non-empty 'steps' list.")

        normalized_steps: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Flow step at index {index} must be an object.")

            normalized_step = dict(step)
            step_id = normalized_step.get("id") or f"step_{index + 1}"
            if not isinstance(step_id, str):
                raise ValueError("Flow step 'id' must be a string.")
            if step_id in seen_ids:
                raise ValueError(f"Duplicate flow step id '{step_id}'.")
            seen_ids.add(step_id)
            normalized_step["id"] = step_id

            tool_name = normalized_step.get("tool")
            if not tool_name or not isinstance(tool_name, str):
                raise ValueError(f"Flow step '{step_id}' requires a string 'tool'.")

            params = normalized_step.get("params")
            if params is None:
                normalized_step["params"] = {}
            elif not isinstance(params, dict):
                raise ValueError(f"Flow step '{step_id}' params must be an object.")

            save_as = normalized_step.get("save_as")
            if save_as is not None and not isinstance(save_as, str):
                raise ValueError(f"Flow step '{step_id}' save_as must be a string when provided.")

            normalized_steps.append(normalized_step)

        spec["steps"] = normalized_steps
        return spec

    def _resolve_flow_params(
        self,
        raw_params: Dict[str, Any],
        inputs: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, value in raw_params.items():
            if isinstance(value, str) and value.startswith("$"):
                resolved[key] = self._resolve_flow_reference(value, inputs, ctx)
            else:
                resolved[key] = value
        return resolved

    def _resolve_flow_reference(
        self,
        expr: str,
        inputs: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> Any:
        if expr.startswith("$inputs."):
            key = expr[len("$inputs."):]
            if key not in inputs:
                raise ValueError(f"Flow reference '{expr}' could not be resolved from inputs.")
            return inputs[key]
        if expr.startswith("$ctx."):
            key = expr[len("$ctx."):]
            if key not in ctx:
                raise ValueError(f"Flow reference '{expr}' could not be resolved from context.")
            return ctx[key]
        return expr

    def _log_flow_step(
        self,
        *,
        flow_name: str,
        flow_run_id: str,
        step_id: str,
        tool_name: str,
        status: str,
        params: Dict[str, Any],
        result: Any,
        error: Optional[Dict[str, Any]],
    ) -> None:
        entry = {
            "flow_run_id": flow_run_id,
            "flow_name": flow_name,
            "step_id": step_id,
            "tool_name": tool_name,
            "status": status,
            "params": self._json_safe(params),
            "result_summary": self._summarize_result(result),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log_file = self._flow_log_file_for(flow_name)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _flow_log_file_for(self, flow_name: str) -> Path:
        safe_name = flow_name.replace("/", "_")
        return self.log_dir / f"flow_{safe_name}.jsonl"


class DependencyManager:
    def __init__(self):
        self.installed_packages: List[str] = self._get_installed_packages()

    def _get_installed_packages(self) -> List[str]:
        return [pkg.metadata['Name'] for pkg in importlib.metadata.distributions()]

    def install_package(self, package_name: str) -> bool:
        if package_name in self.installed_packages:
            return True

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            self.installed_packages.append(package_name)
            return True
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to install dependency: {package_name}")
            return False
