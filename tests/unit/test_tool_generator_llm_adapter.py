import os
import tempfile
import unittest
from unittest.mock import patch

from llm_api import LLMConfig
from tool_generator import ToolGenerator


class ToolGeneratorLLMAdapterTests(unittest.TestCase):
    def _make_generator(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        log_dir = os.path.join(temp_dir.name, "logs")
        tool_dir = os.path.join(temp_dir.name, "tools")
        test_dir = os.path.join(temp_dir.name, "tests")
        config = LLMConfig(provider="openai", api_key="test", model="gpt-4o")
        generator = ToolGenerator(config, log_dir=log_dir, tool_dir=tool_dir, test_dir=test_dir)
        return generator

    @patch("tool_generator.llm_call")
    def test_generate_design_uses_config(self, mock_llm_call):
        mock_llm_call.side_effect = ["design-0", "design-1", "design-2"]
        generator = self._make_generator()

        result = generator.generate_design("sample", "Sample description")

        self.assertEqual(result, "design-2")
        self.assertGreaterEqual(mock_llm_call.call_count, 1)
        for call in mock_llm_call.call_args_list:
            self.assertIs(call.args[1], generator.llm_config)

    @patch("tool_generator.llm_call")
    def test_generate_code_uses_config(self, mock_llm_call):
        mock_llm_call.return_value = "```python\nprint('hello')\n```"
        generator = self._make_generator()
        generator.design = "Design text"

        generator.generate_code("my_tool")

        self.assertIs(mock_llm_call.call_args[0][1], generator.llm_config)

    @patch("tool_generator.llm_call")
    def test_generate_tests_uses_config(self, mock_llm_call):
        mock_llm_call.return_value = "```python\nimport unittest\n```"
        generator = self._make_generator()
        generator.code = "print('hi')"

        generator.generate_tests("my_tool")

        self.assertIs(mock_llm_call.call_args[0][1], generator.llm_config)


if __name__ == "__main__":
    unittest.main()
