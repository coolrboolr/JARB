"""Lightweight JSON-backed storage for deterministic tool flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class FlowLibrary:
    """Persist and retrieve flow specifications from a directory of JSON files."""

    def __init__(self, base_dir: Path | str = "flows") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_flows(self) -> List[str]:
        """Return the list of stored flow names (JSON stem files)."""
        return sorted(path.stem for path in self.base_dir.glob("*.json"))

    def get_flow(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a flow spec from disk if it exists."""
        path = self.base_dir / f"{name}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_flow(self, flow: Dict[str, Any]) -> None:
        """Persist a flow spec to disk under `<name>.json`."""
        name = flow.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("Flow spec must include a string 'name'.")
        path = self.base_dir / f"{name}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(flow, handle, indent=2)

    def delete_flow(self, name: str) -> None:
        """Delete the stored flow spec if it exists."""
        path = self.base_dir / f"{name}.json"
        if path.exists():
            path.unlink()
