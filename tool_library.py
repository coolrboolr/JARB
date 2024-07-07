import os
import types
from typing import Dict, Callable, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolLibrary:
    def __init__(self, tools_dir: str = 'tools'):
        self.tools: Dict[str, Callable] = {}
        self.tools_dir: str = tools_dir
        os.makedirs(self.tools_dir, exist_ok=True)
        self.load_tools()

    def add_tool(self, name: str, function: Callable, code: str) -> None:
        if name in self.tools:
            logger.warning(f"Overwriting existing tool: {name}")
        self.tools[name] = function
        logger.info(f"Added tool: {name}")
        self.save_tool(name, code)

    def get_tool(self, name: str) -> Optional[Callable]:
        if name not in self.tools:
            self.load_tool(name)
        tool = self.tools.get(name)
        if not tool:
            logger.warning(f"Tool not found: {name}")
        return tool

    def list_tools(self) -> list:
        return list(self.tools.keys())

    def remove_tool(self, name: str) -> None:
        tool_file = os.path.join(self.tools_dir, f"{name}.py")
        if os.path.exists(tool_file):
            os.remove(tool_file)
            if name in self.tools:
                del self.tools[name]
            logger.info(f"Removed tool: {name}")
        else:
            logger.warning(f"Cannot remove non-existent tool: {name}")

    def save_tool(self, name: str, code: str) -> None:
        tool_file = os.path.join(self.tools_dir, f"{name}.py")
        with open(tool_file, 'w') as f:
            f.write(code)
        logger.info(f"Saved tool: {name}")

    def load_tools(self) -> None:
        for filename in os.listdir(self.tools_dir):
            if filename.endswith('.py'):
                tool_name = filename[:-3]
                self.load_tool(tool_name)
        logger.info(f"Loaded tools from {self.tools_dir}")

    def load_tool(self, name: str) -> None:
        tool_file = os.path.join(self.tools_dir, f"{name}.py")
        if os.path.exists(tool_file):
            with open(tool_file, 'r') as f:
                code = f.read()
            module = types.ModuleType(name)
            exec(code, module.__dict__)
            function = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith("Test"):
                    function = attr
                    break
            if function:
                self.tools[name] = function
                logger.info(f"Loaded tool: {name}")
            else:
                logger.warning(f"No function found in tool: {name}")
        else:
            logger.warning(f"Could not load tool: {name}")
