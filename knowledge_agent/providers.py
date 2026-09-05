"""
providers.py — Multi-LLM Provider Architecture for Knowledge Agent

Native HTTP REST adapters for Mistral AI, OpenAI, Anthropic, Gemini, Groq, and Ollama.
Zero external SDK dependencies required (pure httpx).
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import httpx
from dotenv import load_dotenv

from . import retry

load_dotenv()


class BaseLLMProvider(ABC):
    """Abstract interface for LLM synthesis engines."""

    name: str = "base"

    def __init__(self, model: Optional[str] = None):
        self.model = model or self.default_model()

    @abstractmethod
    def default_model(self) -> str:
        """Returns the default model name for this provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the required API keys or endpoints are configured in environment."""
        pass

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        """Generates completion text from system and user prompts."""
        pass

    def get_info(self) -> Dict[str, Any]:
        """Returns metadata about the provider."""
        return {
            "name": self.name,
            "model": self.model,
            "configured": self.is_configured()
        }


class MistralProvider(BaseLLMProvider):
    name = "mistral"

    def default_model(self) -> str:
        return os.getenv("MISTRAL_MODEL", "mistral-small-2506")

    def is_configured(self) -> bool:
        return bool(os.getenv("MISTRAL_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        api_key = os.getenv("MISTRAL_API_KEY", "")
        if not api_key:
            return ""

        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # A generation call is not idempotent and costs real money --
                # a dropped connection after the provider already generated a
                # response must not be blindly retried, since we can't tell
                # whether it went through. Only retry on a definite rejection
                # (5xx / rate limit), never on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, headers=headers, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip() or ""
        except Exception as e:
            print(f"Error invoking Mistral AI API ({self.model}): {e}")
        return ""


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def default_model(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""

        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # A generation call is not idempotent and costs real money --
                # a dropped connection after the provider already generated a
                # response must not be blindly retried, since we can't tell
                # whether it went through. Only retry on a definite rejection
                # (5xx / rate limit), never on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, headers=headers, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip() or ""
        except Exception as e:
            print(f"Error invoking OpenAI API ({self.model}): {e}")
        return ""


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def default_model(self) -> str:
        return os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

    def is_configured(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return ""

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # A generation call is not idempotent and costs real money --
                # a dropped connection after the provider already generated a
                # response must not be blindly retried, since we can't tell
                # whether it went through. Only retry on a definite rejection
                # (5xx / rate limit), never on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, headers=headers, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                contents = data.get("content", [])
                if contents and "text" in contents[0]:
                    return contents[0].get("text", "").strip() or ""
        except Exception as e:
            print(f"Error invoking Anthropic API ({self.model}): {e}")
        return ""


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def default_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def is_configured(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return ""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # A generation call is not idempotent and costs real money --
                # a dropped connection after the provider already generated a
                # response must not be blindly retried, since we can't tell
                # whether it went through. Only retry on a definite rejection
                # (5xx / rate limit), never on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, headers=headers, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0].get("text", "").strip() or ""
        except Exception as e:
            print(f"Error invoking Google Gemini API ({self.model}): {e}")
        return ""


class GroqProvider(BaseLLMProvider):
    name = "groq"

    def default_model(self) -> str:
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def is_configured(self) -> bool:
        return bool(os.getenv("GROQ_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return ""

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # A generation call is not idempotent and costs real money --
                # a dropped connection after the provider already generated a
                # response must not be blindly retried, since we can't tell
                # whether it went through. Only retry on a definite rejection
                # (5xx / rate limit), never on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, headers=headers, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip() or ""
        except Exception as e:
            print(f"Error invoking Groq API ({self.model}): {e}")
        return ""


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def default_model(self) -> str:
        return os.getenv("OLLAMA_MODEL", "llama3.2:latest")

    def is_configured(self) -> bool:
        # Ollama runs locally; consider configured if OLLAMA_HOST is set or default is reachable
        return bool(os.getenv("OLLAMA_HOST") or os.getenv("LLM_PROVIDER") == "ollama")

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        url = f"{host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                # Same non-idempotency concern as the other providers: don't
                # retry blind on a connection-level exception.
                res = retry.request_with_retry(
                    lambda: client.post(url, json=payload),
                    retry_on_connection_error=False,
                )
                if res is None:
                    return ""
                res.raise_for_status()
                data = res.json()
                message = data.get("message", {})
                return message.get("content", "").strip() or ""
        except Exception as e:
            print(f"Error invoking Ollama API ({self.model} at {host}): {e}")
        return ""


class MockProvider(BaseLLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-model-v1", canned_response: str = "This is a mock LLM answer."):
        super().__init__(model=model)
        self.canned_response = canned_response

    def default_model(self) -> str:
        return "mock-model-v1"

    def is_configured(self) -> bool:
        return True

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        return self.canned_response


PROVIDER_REGISTRY = {
    "mistral": MistralProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
    "mock": MockProvider
}


def get_provider(provider_name: Optional[str] = None, model: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory resolving the active LLM provider.
    Priority:
    1. Explicit provider_name argument
    2. LLM_PROVIDER environment variable
    3. Auto-detection based on configured environment variables
    4. Default MistralProvider fallback
    """
    chosen = (provider_name or os.getenv("LLM_PROVIDER", "")).strip().lower()

    if chosen in PROVIDER_REGISTRY:
        return PROVIDER_REGISTRY[chosen](model=model)

    # Auto-detection by configured environment keys
    if os.getenv("MISTRAL_API_KEY"):
        return MistralProvider(model=model)
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider(model=model)
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider(model=model)
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return GeminiProvider(model=model)
    if os.getenv("GROQ_API_KEY"):
        return GroqProvider(model=model)
    if os.getenv("OLLAMA_HOST"):
        return OllamaProvider(model=model)

    return MistralProvider(model=model)


def list_providers() -> Dict[str, Dict[str, Any]]:
    """Lists all supported providers and their configuration status."""
    result = {}
    for name, cls in PROVIDER_REGISTRY.items():
        if name == "mock":
            continue
        instance = cls()
        result[name] = instance.get_info()
    return result
