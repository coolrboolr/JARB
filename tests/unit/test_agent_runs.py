import json
import os
import tempfile
import types
import unittest

from agent import Agent


class FakeToolLibrary:
    def __init__(self, tools):
        self._tools = tools

    def list_tools(self):
        return list(self._tools.keys())

    def get_tool(self, name):
        return self._tools.get(name)

    def add_tool(self, name, function, code):  # pragma: no cover - helper stub
        self._tools[name] = function


class AgentRunLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tool_library = FakeToolLibrary({
            "adder": lambda x, y: x + y,
            "boom": self._boom,
        })
        dummy_generator = types.SimpleNamespace()
        dummy_dependency_manager = types.SimpleNamespace(install_package=lambda *args, **kwargs: True)
        self.agent = Agent(
            llm_backend="openai",
            tool_generator=dummy_generator,
            tool_library=self.tool_library,
            dependency_manager=dummy_dependency_manager,
            log_dir=self.temp_dir.name,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _boom(*_args, **_kwargs):
        raise RuntimeError("explode")

    def test_successful_run_logged(self):
        result = self.agent.use_tool("adder", x=2, y=3)
        self.assertEqual(result, 5)

        runs = self.agent.get_tool_runs("adder")
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["status"], "success")
        self.assertIsNone(run["error"])
        self.assertEqual(run["params"], {"x": 2, "y": 3})
        self.assertIn("duration_ms", run)
        self.assertGreaterEqual(run["duration_ms"], 0)
        self.assertEqual(run["result_summary"], "5")

        log_file = os.path.join(self.temp_dir.name, "adder.jsonl")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["status"], "success")

    def test_failed_run_logged_with_error(self):
        with self.assertRaises(RuntimeError):
            self.agent.use_tool("boom")

        runs = self.agent.get_tool_runs("boom")
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["status"], "error")
        self.assertIsNotNone(run["error"])
        self.assertEqual(run["error"]["type"], "RuntimeError")
        self.assertIsNone(run["result_summary"])

    def test_get_tool_runs_respects_limit_and_order(self):
        for i in range(5):
            self.agent.use_tool("adder", x=i, y=i)

        runs = self.agent.get_tool_runs("adder", limit=3)
        self.assertEqual(len(runs), 3)
        latest = runs[0]
        self.assertEqual(latest["params"], {"x": 4, "y": 4})
        oldest_of_slice = runs[-1]
        self.assertEqual(oldest_of_slice["params"], {"x": 2, "y": 2})


if __name__ == "__main__":
    unittest.main()
