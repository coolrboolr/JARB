import os
import sys
import tempfile
import types
import unittest


def _ensure_dummy_llm_modules():
    if "anthropic" not in sys.modules:
        class _DummyAnthropicMessages:
            def create(self, **kwargs):
                class _Response:
                    content = [types.SimpleNamespace(text="")]

                return _Response()

        class _DummyAnthropicClient:
            def __init__(self, api_key=None):
                self.messages = _DummyAnthropicMessages()

        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=_DummyAnthropicClient)

    if "openai" not in sys.modules:
        class _DummyCompletions:
            def create(self, **kwargs):
                class _Message:
                    content = ""

                class _Choice:
                    message = _Message()

                class _Response:
                    choices = [_Choice()]

                return _Response()

        class _DummyChat:
            def __init__(self):
                self.completions = _DummyCompletions()

        sys.modules["openai"] = types.SimpleNamespace(chat=_DummyChat(), api_key="")


_ensure_dummy_llm_modules()

from agent import Agent
from tool_library import ToolLibrary


class FakeToolGenerator:
    """Deterministic generator that returns simple increment code."""

    def create_tool(self, name: str, description: str) -> str:
        return (
            f"def {name}(x: int) -> int:\n"
            "    \"\"\"Simple fake tool used for testing.\"\"\"\n"
            "    return x + 1\n"
        )


class FakeDependencyManager:
    def __init__(self):
        self.packages = []

    def install_package(self, package_name: str) -> bool:
        self.packages.append(package_name)
        return True


class AgentIntegrationTest(unittest.TestCase):
    def test_create_and_use_tool_with_fake_generator(self):
        with tempfile.TemporaryDirectory() as temp_tools_dir:
            tool_library = ToolLibrary(tools_dir=temp_tools_dir)
            agent = Agent(
                tool_generator=FakeToolGenerator(),
                tool_library=tool_library,
                dependency_manager=FakeDependencyManager(),
            )

            agent.create_tool("fake_tool", "A fake tool that adds 1")

            tool_path = os.path.join(temp_tools_dir, "fake_tool.py")
            self.assertTrue(os.path.exists(tool_path), "Tool file should be saved in temp dir")
            self.assertIn("fake_tool", agent.list_tools())

            result = agent.use_tool("fake_tool", x=2)
            self.assertEqual(result, 3)

            description = agent.describe_tool("fake_tool")
            self.assertEqual(description["name"], "fake_tool")
            self.assertEqual(description["docstring"], "Simple fake tool used for testing.")
            param = description["parameters"][0]
            self.assertTrue(param["required"])
            self.assertEqual(param["annotation"]["type"], "int")


if __name__ == "__main__":
    unittest.main()
