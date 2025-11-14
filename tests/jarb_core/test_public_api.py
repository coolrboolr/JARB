import json
import os
import tempfile
import unittest

import jarb_core


class FakeToolGenerator:
    def create_tool(self, name: str, description: str) -> str:  # pragma: no cover - tiny helper
        return (
            f"def {name}(value: int) -> int:\n"
            "    \"\"\"Deterministic fake tool.\"\"\"\n"
            "    return value + 1\n"
        )


class JarbCorePublicApiTests(unittest.TestCase):
    def _configure(self, root_dir: str):
        return jarb_core.configure(
            llm_backend="openai",
            api_key="unit-test",
            tools_dir=os.path.join(root_dir, "tools"),
            log_dir=os.path.join(root_dir, "logs"),
            flow_dir=os.path.join(root_dir, "flows"),
            load_env=False,
            tool_generator=FakeToolGenerator(),
        )

    def test_tool_lifecycle_and_reconfigure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._configure(tmp)
            jarb_core.create_tool("increment", "Adds one")

            tools = jarb_core.list_tools()
            self.assertIn("increment", tools)

            description = jarb_core.describe_tool("increment")
            self.assertEqual(description["name"], "increment")
            self.assertIn("Deterministic", description["docstring"])

            result = jarb_core.use_tool("increment", value=2)
            self.assertEqual(result, 3)

            runs = jarb_core.get_tool_runs("increment")
            self.assertTrue(runs, "Tool run should be logged")

            # Reconfigure to a clean directory and ensure state resets.
            fresh_root = os.path.join(tmp, "fresh")
            os.makedirs(fresh_root, exist_ok=True)
            self._configure(fresh_root)
            self.assertEqual(jarb_core.list_tools(), [])

    def test_flow_helpers_delegate_to_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._configure(tmp)
            jarb_core.create_tool("increment", "Adds one")

            flow_spec = {
                "name": "increment_flow",
                "inputs": ["value"],
                "steps": [
                    {
                        "id": "first",
                        "tool": "increment",
                        "params": {"value": "$inputs.value"},
                        "save_as": "after_first",
                    },
                    {
                        "id": "second",
                        "tool": "increment",
                        "params": {"value": "$ctx.after_first"},
                        "save_as": "after_second",
                    },
                ],
                "output": "$ctx.after_second",
            }

            jarb_core.create_flow(json.loads(json.dumps(flow_spec)))
            self.assertIn("increment_flow", jarb_core.list_flows())

            described = jarb_core.describe_flow("increment_flow")
            self.assertEqual(described["name"], "increment_flow")

            result = jarb_core.run_flow("increment_flow", {"value": 1})
            self.assertEqual(result, 3)

            runs = jarb_core.get_flow_runs("increment_flow")
            self.assertTrue(runs, "Flow run should be logged")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
