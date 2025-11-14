import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Optional

try:  # pragma: no cover - imported for runtime use
    import anthropic  # type: ignore
except ImportError:  # pragma: no cover - fallback enables tests without the package installed
    anthropic = SimpleNamespace(Anthropic=None)  # type: ignore

try:  # pragma: no cover
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = SimpleNamespace(  # type: ignore
        api_key=None,
        chat=SimpleNamespace(completions=SimpleNamespace(create=None)),
    )


DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL = "claude-3-sonnet-20240229"


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    client_factory: Optional[Callable[[str], object]] = None


def load_llm_config(provider: str) -> LLMConfig:
    normalized_provider = provider.strip().lower()

    if normalized_provider == "openai":
        api_key = os.getenv("OPENAI_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_KEY environment variable is required for OpenAI backend.")
        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return LLMConfig(provider="openai", api_key=api_key, model=model)

    if normalized_provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is required for Anthropic backend."
            )
        model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        return LLMConfig(provider="anthropic", api_key=api_key, model=model)

    raise ValueError(f"Unsupported LLM provider '{provider}'.")


def llm_call(prompt: str, config: LLMConfig, context: Optional[str] = None) -> str:
    provider = config.provider.strip().lower()

    if provider == "openai":
        client = config.client_factory(config.api_key) if config.client_factory else openai
        if not config.client_factory:
            has_create = (
                hasattr(client, "chat")
                and hasattr(client.chat, "completions")
                and hasattr(client.chat.completions, "create")
            )
            if not has_create:
                raise RuntimeError("OpenAI client library is not installed. Install the 'openai' package.")
            openai.api_key = config.api_key

        messages = []
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return response.choices[0].message.content.strip()

    if provider == "anthropic":
        client = None
        if config.client_factory:
            client = config.client_factory(config.api_key)
        else:
            anthropic_cls = getattr(anthropic, "Anthropic", None)
            if anthropic_cls is None:
                raise RuntimeError("Anthropic client library is not installed. Install the 'anthropic' package.")
            client = anthropic_cls(api_key=config.api_key)

        messages = []
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": prompt})

        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=messages,
        )

        content = getattr(response, "content", None)
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                return str(first.get("text", "")).strip()
            return str(getattr(first, "text", "")).strip()
        return str(content or "").strip()

    raise ValueError(f"Unsupported LLM provider '{config.provider}'.")
