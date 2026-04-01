"""Provider registry — maps models to providers and manages health status."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from kestrel.config import Settings
from kestrel.providers.anthropic import AnthropicProvider
from kestrel.providers.base import LLMProvider
from kestrel.providers.cohere import CohereProvider
from kestrel.providers.gemini import GeminiProvider
from kestrel.providers.groq import GroqProvider
from kestrel.providers.mistral import MistralProvider
from kestrel.providers.openai import OpenAIProvider
from kestrel.providers.together import TogetherProvider
from kestrel.providers.xai import XaiProvider

logger = logging.getLogger(__name__)

# Model prefix → provider name
_MODEL_PROVIDER_MAP: dict[str, str] = {
    # OpenAI
    "gpt-": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    # Anthropic
    "claude-": "anthropic",
    # Google
    "gemini-": "gemini",
    # Groq (Llama, Mixtral, etc.)
    "llama": "groq",
    "mixtral": "groq",
    "gemma": "groq",
    # Mistral
    "mistral-": "mistral",
    "codestral": "mistral",
    "pixtral": "mistral",
    # Cohere
    "command-": "cohere",
    # Together AI (uses full model paths)
    "meta-llama/": "together",
    "mistralai/": "together",
    "qwen/": "together",
    # xAI
    "grok-": "xai",
}

# Model equivalence for failover: model → list of fallback models (in priority order)
MODEL_EQUIVALENTS: dict[str, list[str]] = {
    # Premium tier
    "gpt-4o": ["claude-sonnet-4-6", "gemini-1.5-pro"],
    "claude-sonnet-4-6": ["gpt-4o", "gemini-1.5-pro"],
    "claude-opus-4-6": ["gpt-4o", "claude-sonnet-4-6"],
    "gemini-1.5-pro": ["gpt-4o", "claude-sonnet-4-6"],
    # Standard tier
    "gpt-4o-mini": ["claude-haiku-4-5", "gemini-1.5-flash"],
    "claude-haiku-4-5": ["gpt-4o-mini", "gemini-1.5-flash"],
    "gemini-1.5-flash": ["gpt-4o-mini", "claude-haiku-4-5"],
    # Economy tier (Groq)
    "llama-3.1-8b-instant": ["gpt-4o-mini", "gemini-1.5-flash"],
    "llama-3.1-70b-versatile": ["gpt-4o-mini", "claude-haiku-4-5"],
    # Mistral
    "mistral-large-latest": ["gpt-4o", "claude-sonnet-4-6"],
    "mistral-small-latest": ["gpt-4o-mini", "claude-haiku-4-5"],
    # Cohere
    "command-r-plus": ["gpt-4o", "claude-sonnet-4-6"],
    "command-r": ["gpt-4o-mini", "claude-haiku-4-5"],
    # xAI
    "grok-3": ["gpt-4o", "claude-sonnet-4-6"],
    "grok-3-mini": ["gpt-4o-mini", "claude-haiku-4-5"],
    "grok-4-0709": ["gpt-4o", "claude-sonnet-4-6"],
}


@dataclass
class ProviderHealth:
    """Health status of a provider."""

    is_available: bool = True
    last_check: float = 0.0
    last_latency_ms: int | None = None
    consecutive_failures: int = 0


@dataclass
class ProviderRegistry:
    """Manages provider instances and their health status."""

    _providers: dict[str, LLMProvider] = field(default_factory=dict)
    _health: dict[str, ProviderHealth] = field(default_factory=dict)

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        http_client: httpx.AsyncClient,
        *,
        provider_api_keys: dict[str, str] | None = None,
    ) -> ProviderRegistry:
        """Create a registry from settings and operator-provided API keys."""
        keys = provider_api_keys or {}
        registry = cls()

        if keys.get("openai"):
            registry.register(
                "openai",
                OpenAIProvider(
                    api_key=keys["openai"],
                    base_url=settings.openai_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("anthropic"):
            registry.register(
                "anthropic",
                AnthropicProvider(
                    api_key=keys["anthropic"],
                    base_url=settings.anthropic_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("gemini"):
            registry.register(
                "gemini",
                GeminiProvider(
                    api_key=keys["gemini"],
                    base_url=settings.gemini_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("groq"):
            registry.register(
                "groq",
                GroqProvider(
                    api_key=keys["groq"],
                    base_url=settings.groq_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("mistral"):
            registry.register(
                "mistral",
                MistralProvider(
                    api_key=keys["mistral"],
                    base_url=settings.mistral_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("cohere"):
            registry.register(
                "cohere",
                CohereProvider(
                    api_key=keys["cohere"],
                    base_url=settings.cohere_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("together"):
            registry.register(
                "together",
                TogetherProvider(
                    api_key=keys["together"],
                    base_url=settings.together_base_url,
                    http_client=http_client,
                ),
            )

        if keys.get("xai"):
            registry.register(
                "xai",
                XaiProvider(
                    api_key=keys["xai"],
                    base_url=settings.xai_base_url,
                    http_client=http_client,
                ),
            )

        return registry

    def register(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider
        self._health[name] = ProviderHealth()

    def get_provider(self, provider_name: str) -> LLMProvider | None:
        return self._providers.get(provider_name)

    def get_provider_for_model(self, model: str) -> LLMProvider | None:
        """Look up the provider for a given model name."""
        provider_name = self.resolve_provider_name(model)
        if provider_name:
            return self._providers.get(provider_name)
        return None

    def resolve_provider_name(self, model: str) -> str | None:
        """Determine which provider handles a given model."""
        model_lower = model.lower()
        for prefix, provider_name in _MODEL_PROVIDER_MAP.items():
            if model_lower.startswith(prefix) and provider_name in self._providers:
                return provider_name
        return None

    def get_fallback_providers(self, model: str) -> list[tuple[str, str]]:
        """Get fallback (provider_name, model_name) pairs for failover."""
        equivalents = MODEL_EQUIVALENTS.get(model, [])
        fallbacks = []
        for alt_model in equivalents:
            provider_name = self.resolve_provider_name(alt_model)
            if provider_name and self.is_healthy(provider_name):
                fallbacks.append((provider_name, alt_model))
        return fallbacks

    def is_healthy(self, provider_name: str) -> bool:
        health = self._health.get(provider_name)
        return health is not None and health.is_available

    def mark_healthy(self, provider_name: str, latency_ms: int) -> None:
        health = self._health.get(provider_name)
        if health:
            health.is_available = True
            health.last_check = time.monotonic()
            health.last_latency_ms = latency_ms
            health.consecutive_failures = 0

    def mark_unhealthy(self, provider_name: str) -> None:
        health = self._health.get(provider_name)
        if health:
            health.consecutive_failures += 1
            if health.consecutive_failures >= 3:
                health.is_available = False
                health.last_check = time.monotonic()

    @property
    def available_providers(self) -> list[str]:
        return [name for name, health in self._health.items() if health.is_available]

    def get_health_status(self) -> dict[str, Any]:
        """Return health status for all providers (for /health endpoint)."""
        return {
            name: {
                "available": h.is_available,
                "last_latency_ms": h.last_latency_ms,
                "consecutive_failures": h.consecutive_failures,
            }
            for name, h in self._health.items()
        }
