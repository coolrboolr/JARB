import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from llm_api import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OPENAI_MODEL,
    LLMConfig,
    llm_call,
    load_llm_config,
)


class LoadLLMConfigTests(unittest.TestCase):
    def test_load_openai_config_reads_environment(self):
        with patch.dict(os.environ, {"OPENAI_KEY": "test-key", "OPENAI_MODEL": "gpt-test"}, clear=False):
            config = load_llm_config("openai")

        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.model, "gpt-test")
        self.assertEqual(config.temperature, 0.0)
        self.assertEqual(config.max_tokens, 1024)

    def test_load_anthropic_config_reads_environment(self):
        env = {"ANTHROPIC_API_KEY": "anth-key", "ANTHROPIC_MODEL": "claude-test"}
        with patch.dict(os.environ, env, clear=False):
            config = load_llm_config("anthropic")

        self.assertEqual(config.provider, "anthropic")
        self.assertEqual(config.api_key, "anth-key")
        self.assertEqual(config.model, "claude-test")

    def test_missing_env_var_raises_runtime_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                load_llm_config("openai")


class LlmCallTests(unittest.TestCase):
    @patch("llm_api.openai")
    def test_llm_call_openai_forwards_prompt_and_context(self, mock_openai):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="  hello world  "))]
        )
        mock_openai.chat.completions.create.return_value = response

        config = LLMConfig(provider="openai", api_key="abc", model=DEFAULT_OPENAI_MODEL)
        result = llm_call("prompt", config, context="context text")

        self.assertEqual(result, "hello world")
        self.assertEqual(mock_openai.api_key, "abc")
        mock_openai.chat.completions.create.assert_called_once()
        _, kwargs = mock_openai.chat.completions.create.call_args
        self.assertEqual(kwargs["model"], DEFAULT_OPENAI_MODEL)
        self.assertEqual(kwargs["temperature"], config.temperature)
        self.assertEqual(kwargs["max_tokens"], config.max_tokens)
        self.assertEqual(
            kwargs["messages"],
            [
                {"role": "assistant", "content": "context text"},
                {"role": "user", "content": "prompt"},
            ],
        )

    @patch("llm_api.anthropic.Anthropic")
    def test_llm_call_anthropic_uses_client(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_response = SimpleNamespace(content=[SimpleNamespace(text="anthropic reply")])
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        config = LLMConfig(provider="anthropic", api_key="key", model=DEFAULT_ANTHROPIC_MODEL)
        result = llm_call("question", config, context="prior context")

        self.assertEqual(result, "anthropic reply")
        mock_anthropic_cls.assert_called_once_with(api_key="key")
        mock_client.messages.create.assert_called_once()
        _, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs["model"], DEFAULT_ANTHROPIC_MODEL)
        self.assertEqual(kwargs["max_tokens"], config.max_tokens)
        self.assertEqual(kwargs["temperature"], config.temperature)
        self.assertEqual(
            kwargs["messages"],
            [
                {"role": "assistant", "content": "prior context"},
                {"role": "user", "content": "question"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
