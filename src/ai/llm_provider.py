"""LLM provider adapters (OpenAI and Ollama) with safe disabled fallback."""

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface."""

    provider_name = "disabled"
    model = "none"
    enabled = False
    status = "LLM disabled."

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> Optional[str]:
        """Return model text response, or None if unavailable."""


class DisabledLLMProvider(BaseLLMProvider):
    """No-op provider used when LLM mode is off or misconfigured."""

    def __init__(self, reason: str = "LLM disabled via settings."):
        self.status = reason

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> Optional[str]:
        return None


class OllamaLLMProvider(BaseLLMProvider):
    """Local Ollama-backed provider for edge/local inference."""

    provider_name = "ollama"
    enabled = True

    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.status = f"LLM enabled via Ollama ({self.model})."

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> Optional[str]:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
            data = json.loads(body)
            message = data.get("message", {})
            content = message.get("content")
            return content.strip() if isinstance(content, str) else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI SDK-backed provider."""

    provider_name = "openai"
    enabled = True

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self.status = f"LLM enabled via OpenAI ({self.model})."

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> Optional[str]:
        try:
            from openai import OpenAI
        except ImportError:
            return None

        try:
            client = OpenAI(api_key=self.api_key)
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            text = getattr(response, "output_text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            return None
        return None


def build_llm_provider_from_env() -> BaseLLMProvider:
    """Build provider using environment configuration."""
    enabled = _as_bool(os.getenv("TRAININGLOGS_LLM_ENABLED", "false"))
    if not enabled:
        return DisabledLLMProvider("LLM disabled. Set TRAININGLOGS_LLM_ENABLED=true to enable.")

    provider = os.getenv("TRAININGLOGS_LLM_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        model = os.getenv("TRAININGLOGS_OLLAMA_MODEL", "qwen2.5:3b-instruct")
        base_url = os.getenv("TRAININGLOGS_OLLAMA_URL", "http://localhost:11434")
        return OllamaLLMProvider(model=model, base_url=base_url)

    if provider == "openai":
        model = os.getenv("TRAININGLOGS_OPENAI_MODEL", "gpt-4o-mini")
        api_key = os.getenv("TRAININGLOGS_OPENAI_API_KEY", "").strip()
        if not api_key:
            return DisabledLLMProvider(
                "OpenAI provider selected but TRAININGLOGS_OPENAI_API_KEY is missing."
            )
        return OpenAILLMProvider(model=model, api_key=api_key)

    return DisabledLLMProvider(f"Unknown LLM provider '{provider}'.")

