import tempfile
import textwrap
import types
import unittest

from agent import Agent
from tool_library import ToolLibrary


def _add_tool(library: ToolLibrary, name: str, code: str) -> None:
    source = textwrap.dedent(code)
    namespace = {}
    exec(source, namespace)
    library.add_tool(name, namespace[name], source)


class AgentCatalogTests(unittest.TestCase):
    def _make_agent(self, tool_sources):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        library = ToolLibrary(tmp.name)
        for name, code in tool_sources.items():
            _add_tool(library, name, code)

        dummy_generator = types.SimpleNamespace()
        dummy_dependency_manager = types.SimpleNamespace(install_package=lambda *args, **kwargs: True)
        return Agent(
            llm_backend="openai",
            tool_generator=dummy_generator,
            tool_library=library,
            dependency_manager=dummy_dependency_manager,
        )

    def test_get_tool_catalog_includes_all_tools(self):
        tool_sources = {
            "foo": """
                def foo(a, b):
                    \"""Foo tool doc.\"""
                    return a - b
            """,
            "bar": """
                def bar(x: int, y: int = 0) -> int:
                    \"""Bar tool doc.\"""
                    return x + y
            """,
            "typed": """
                from typing import Optional

                def typed(payload: Optional[dict], flag: bool = False):
                    \"""Typed tool doc.\"""
                    return payload if flag else None
            """,
        }

        agent = self._make_agent(tool_sources)

        catalog = agent.get_tool_catalog()

        names = {entry["name"] for entry in catalog}
        self.assertEqual(names, {"foo", "bar", "typed"})
        foo_entry = next(entry for entry in catalog if entry["name"] == "foo")
        self.assertEqual(foo_entry["docstring"], "Foo tool doc.")
        self.assertTrue(isinstance(foo_entry["parameters"], list))
        self.assertIn("return_annotation", foo_entry)

        bar_entry = next(entry for entry in catalog if entry["name"] == "bar")
        bar_params = {param["name"]: param for param in bar_entry["parameters"]}
        self.assertTrue(bar_params["x"]["required"])
        self.assertEqual(bar_params["x"]["annotation"]["type"], "int")
        self.assertFalse(bar_params["y"]["required"])
        self.assertEqual(bar_params["y"]["annotation"]["type"], "int")

        typed_entry = next(entry for entry in catalog if entry["name"] == "typed")
        typed_params = {param["name"]: param for param in typed_entry["parameters"]}
        self.assertEqual(typed_params["payload"]["annotation"]["type"], "json")
        self.assertTrue(typed_params["payload"]["required"])
        self.assertEqual(typed_params["flag"]["annotation"]["type"], "bool")
        self.assertFalse(typed_params["flag"]["required"])

    def test_get_tool_catalog_skips_broken_tools(self):
        tool_sources = {
            "good": """
                def good():
                    \"""Good doc.\"""
                    return "ok"
            """,
            "broken": """
                def broken():
                    \"""Broken doc.\"""
                    return "boom"
            """,
        }

        agent = self._make_agent(tool_sources)
        original_describe = agent.tool_library.describe_tool

        def fake_describe(self, name):
            if name == "broken":
                raise RuntimeError("cannot inspect tool")
            return original_describe(name)

        agent.tool_library.describe_tool = types.MethodType(fake_describe, agent.tool_library)

        catalog = agent.get_tool_catalog()

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["name"], "good")


if __name__ == "__main__":
    unittest.main()
