import json
import os
import tempfile
import unittest

from agent import Agent
from flow_library import FlowLibrary
from tool_library import ToolLibrary


class NoopToolGenerator:
    def create_tool(self, name: str, description: str) -> str:  # pragma: no cover - helper only
        raise NotImplementedError


class NoopDependencyManager:
    def install_package(self, package_name: str) -> bool:  # pragma: no cover - helper only
        return True


def _add_tool(tool_library: ToolLibrary, name: str, body: str):
    namespace = {}
    exec(body, namespace)
    tool_library.add_tool(name, namespace[name], body)


class AgentFlowTests(unittest.TestCase):
    def _make_agent(self, root_dir: str) -> Agent:
        tools_dir = os.path.join(root_dir, "tools")
        flows_dir = os.path.join(root_dir, "flows")
        logs_dir = os.path.join(root_dir, "logs")
        tool_library = ToolLibrary(tools_dir=tools_dir)
        flow_library = FlowLibrary(flows_dir)
        return Agent(
            llm_backend="openai",
            api_key="unit-test",
            tool_generator=NoopToolGenerator(),
            tool_library=tool_library,
            dependency_manager=NoopDependencyManager(),
            log_dir=logs_dir,
            flow_library=flow_library,
            tools_dir=tools_dir,
            flow_dir=flows_dir,
        )

    def test_successful_flow_execution_and_logging(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self._make_agent(tmp)

            _add_tool(agent.tool_library, "double", "def double(value):\n    return value * 2\n")
            _add_tool(agent.tool_library, "add_one", "def add_one(value):\n    return value + 1\n")

            flow_spec = {
                "name": "math_chain",
                "description": "double then add one",
                "inputs": ["value"],
                "steps": [
                    {"id": "first", "tool": "double", "params": {"value": "$inputs.value"}, "save_as": "doubled"},
                    {"id": "second", "tool": "add_one", "params": {"value": "$ctx.doubled"}, "save_as": "result"},
                ],
                "output": "$ctx.result",
            }

            agent.create_flow(json.loads(json.dumps(flow_spec)))
            output = agent.run_flow("math_chain", {"value": 3})
            self.assertEqual(output, 7)

            runs = agent.get_flow_runs("math_chain")
            self.assertTrue(runs)
            self.assertEqual(runs[0]["status"], "success")

            log_path = os.path.join(tmp, "logs", "flow_math_chain.jsonl")
            with open(log_path, "r", encoding="utf-8") as handle:
                entries = [json.loads(line) for line in handle if line.strip()]
            self.assertEqual(len(entries), 2)
            self.assertTrue(all(entry["status"] == "success" for entry in entries))

    def test_flow_failure_logs_error_and_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self._make_agent(tmp)

            failing_body = (
                "def explode(value):\n"
                "    raise RuntimeError(\"Boom!\")\n"
            )
            _add_tool(agent.tool_library, "explode", failing_body)

            flow_spec = {
                "name": "failing_flow",
                "steps": [
                    {"id": "explode", "tool": "explode", "params": {"value": 1}},
                ],
            }

            agent.create_flow(flow_spec)
            with self.assertRaises(RuntimeError):
                agent.run_flow("failing_flow", {})

            runs = agent.get_flow_runs("failing_flow")
            self.assertTrue(runs)
            self.assertEqual(runs[0]["status"], "error")
            self.assertEqual(runs[0]["error"]["type"], "RuntimeError")

    def test_flow_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self._make_agent(tmp)
            with self.assertRaises(ValueError):
                agent.create_flow({"steps": []})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
