import inspect
import logging
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, get_args, get_origin
from collections.abc import Mapping as MappingABC, MutableMapping, MutableSequence, Sequence as SequenceABC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UNION_TYPE = getattr(types, "UnionType", None)


@dataclass
class ToolRecord:
    function: Callable
    path: Path
    signature: inspect.Signature
    docstring: Optional[str]
    last_loaded: float


class ToolLibrary:
    def __init__(self, tools_dir: str | Path = "tools"):
        self.tools_dir = Path(tools_dir)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, ToolRecord] = {}
        self.load_tools()

    def add_tool(self, name: str, function: Optional[Callable], code: str) -> None:
        if (self.tools_dir / f"{name}.py").exists():
            logger.warning("Overwriting existing tool: %s", name)
        self._write_tool_file(name, code)
        self.load_tool(name)

    def get_tool(self, name: str) -> Optional[Callable]:
        record = self._ensure_record(name)
        return record.function if record else None

    def get_tool_record(self, name: str) -> ToolRecord:
        record = self._ensure_record(name)
        if not record:
            raise FileNotFoundError(f"The tool {name} does not exist or could not be loaded.")
        return record

    def get_tool_signature(self, name: str) -> inspect.Signature:
        return self.get_tool_record(name).signature

    def get_tool_source(self, name: str) -> str:
        path = self.tools_dir / f"{name}.py"
        if not path.exists():
            raise FileNotFoundError(f"The tool {name} does not exist or could not be loaded.")
        return path.read_text(encoding="utf-8")

    def describe_tool(self, name: str) -> Dict[str, Any]:
        record = self.get_tool_record(name)
        parameters: List[Dict[str, Any]] = []
        for param in record.signature.parameters.values():
            parameters.append(self._build_parameter_metadata(param))

        return {
            "name": name,
            "docstring": record.docstring,
            "parameters": parameters,
            "return_annotation": None
            if record.signature.return_annotation is inspect._empty
            else record.signature.return_annotation,
        }

    def list_tools(self) -> List[str]:
        return sorted(self.records.keys())

    def remove_tool(self, name: str) -> None:
        path = self.tools_dir / f"{name}.py"
        if path.exists():
            path.unlink()
            self.records.pop(name, None)
            logger.info("Removed tool: %s", name)
        else:
            logger.warning("Cannot remove non-existent tool: %s", name)

    def load_tools(self) -> None:
        for file in self.tools_dir.glob("*.py"):
            self._load_tool_from_path(file)
        logger.info("Loaded tools from %s", self.tools_dir)

    def load_tool(self, name: str) -> None:
        path = self.tools_dir / f"{name}.py"
        if not path.exists():
            logger.warning("Could not load tool: %s", name)
            return
        self._load_tool_from_path(path)

    def _write_tool_file(self, name: str, code: str) -> None:
        path = self.tools_dir / f"{name}.py"
        path.write_text(code, encoding="utf-8")
        logger.info("Saved tool: %s", name)

    def _ensure_record(self, name: str) -> Optional[ToolRecord]:
        path = self.tools_dir / f"{name}.py"
        record = self.records.get(name)
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            self.records.pop(name, None)
            return None

        if not record or mtime > record.last_loaded:
            self.load_tool(name)
            record = self.records.get(name)
        return record

    def _load_tool_from_path(self, path: Path) -> None:
        name = path.stem
        code = path.read_text(encoding="utf-8")
        module = types.ModuleType(name)
        exec(code, module.__dict__)
        function = getattr(module, name, None)
        if not callable(function):
            logger.warning("No callable named '%s' found in %s", name, path)
            return

        record = ToolRecord(
            function=function,
            path=path,
            signature=inspect.signature(function),
            docstring=inspect.getdoc(function),
            last_loaded=path.stat().st_mtime,
        )
        self.records[name] = record
        logger.info("Loaded tool: %s", name)

    def _build_parameter_metadata(self, parameter: inspect.Parameter) -> Dict[str, Any]:
        default_value = None if parameter.default is inspect._empty else parameter.default
        required = (
            parameter.default is inspect._empty
            and parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        )

        return {
            "name": parameter.name,
            "kind": parameter.kind.name,
            "default": default_value,
            "required": required,
            "annotation": self._describe_annotation(parameter.annotation),
        }

    def _describe_annotation(self, annotation: Any) -> Dict[str, Optional[str]]:
        descriptor: Dict[str, Optional[str]] = {
            "type": None,
            "raw": None if annotation is inspect._empty else self._stringify(annotation),
        }

        if annotation is inspect._empty:
            descriptor["type"] = "any"
            return descriptor

        descriptor["type"] = self._infer_annotation_type(annotation)
        return descriptor

    def _stringify(self, annotation: Any) -> str:
        try:
            return str(annotation)
        except Exception:  # pragma: no cover - defensive
            return repr(annotation)

    def _infer_annotation_type(self, annotation: Any) -> str:
        primitives = {
            bool: "bool",
            int: "int",
            float: "float",
            str: "str",
        }

        if annotation in primitives:
            return primitives[annotation]

        if isinstance(annotation, type):
            for primitive, label in primitives.items():
                try:
                    if issubclass(annotation, primitive):
                        return label
                except TypeError:
                    continue
            if self._is_json_like(annotation):
                return "json"

        origin = get_origin(annotation)
        if origin:
            if origin in (list, tuple, set):
                return "json"
            if origin in (dict, MappingABC, MutableMapping, SequenceABC, MutableSequence):
                return "json"
            if origin in (typing.Union, UNION_TYPE):
                args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
                if len(args) == 1:
                    return self._infer_annotation_type(args[0])
                return "any"

        if annotation in (dict, list, tuple, set):
            return "json"

        return "any"

    def _is_json_like(self, annotation: Any) -> bool:
        json_like = (dict, list, tuple, set, MappingABC, MutableMapping, SequenceABC, MutableSequence)
        for candidate in json_like:
            try:
                if issubclass(annotation, candidate):
                    return True
            except TypeError:
                continue
        return False
