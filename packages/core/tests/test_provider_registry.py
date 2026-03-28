"""Tests for provider registry and failover logic."""

from __future__ import annotations

import httpx

from kestrel.config import Settings
from kestrel.services.provider_registry import ProviderRegistry


def _make_registry(**api_keys: str) -> ProviderRegistry:
    """Create a registry with the specified provider keys."""
    settings = Settings(
        dev_mode=True,
        openai_base_url="https://api.openai.com/v1",
        anthropic_base_url="https://api.anthropic.com/v1",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        groq_base_url="https://api.groq.com/openai/v1",
    )
    return ProviderRegistry.from_settings(
        settings,
        httpx.AsyncClient(),
        provider_api_keys=api_keys,
    )


class TestProviderResolution:
    def test_gpt_model_resolves_to_openai(self) -> None:
        registry = _make_registry(openai="sk-test")
        assert registry.resolve_provider_name("gpt-4o") == "openai"
        assert registry.resolve_provider_name("gpt-4o-mini") == "openai"

    def test_claude_model_resolves_to_anthropic(self) -> None:
        registry = _make_registry(anthropic="sk-test")
        assert registry.resolve_provider_name("claude-sonnet-4-6") == "anthropic"
        assert registry.resolve_provider_name("claude-haiku-4-5") == "anthropic"

    def test_gemini_model_resolves_to_gemini(self) -> None:
        registry = _make_registry(gemini="key-test")
        assert registry.resolve_provider_name("gemini-1.5-flash") == "gemini"
        assert registry.resolve_provider_name("gemini-1.5-pro") == "gemini"

    def test_llama_model_resolves_to_groq(self) -> None:
        registry = _make_registry(groq="gsk-test")
        assert registry.resolve_provider_name("llama-3.1-8b-instant") == "groq"

    def test_unknown_model_returns_none(self) -> None:
        registry = _make_registry(openai="sk-test")
        assert registry.resolve_provider_name("unknown-model-xyz") is None

    def test_model_without_provider_key_returns_none(self) -> None:
        registry = _make_registry(openai="sk-test")
        # Claude model but no Anthropic key
        assert registry.resolve_provider_name("claude-sonnet-4-6") is None

    def test_get_provider_for_model(self) -> None:
        registry = _make_registry(openai="sk-test", anthropic="sk-test")
        provider = registry.get_provider_for_model("claude-sonnet-4-6")
        assert provider is not None
        assert provider.name == "anthropic"


class TestHealthTracking:
    def test_new_providers_are_healthy(self) -> None:
        registry = _make_registry(openai="sk-test")
        assert registry.is_healthy("openai")

    def test_mark_unhealthy_after_threshold(self) -> None:
        registry = _make_registry(openai="sk-test")
        # Takes 3 consecutive failures to mark unhealthy
        registry.mark_unhealthy("openai")
        assert registry.is_healthy("openai")
        registry.mark_unhealthy("openai")
        assert registry.is_healthy("openai")
        registry.mark_unhealthy("openai")
        assert not registry.is_healthy("openai")

    def test_mark_healthy_resets_failures(self) -> None:
        registry = _make_registry(openai="sk-test")
        registry.mark_unhealthy("openai")
        registry.mark_unhealthy("openai")
        registry.mark_healthy("openai", latency_ms=50)
        assert registry.is_healthy("openai")
        # Should need 3 more failures after reset
        registry.mark_unhealthy("openai")
        registry.mark_unhealthy("openai")
        assert registry.is_healthy("openai")

    def test_available_providers(self) -> None:
        registry = _make_registry(openai="sk-test", anthropic="sk-test")
        assert set(registry.available_providers) == {"openai", "anthropic"}

        # Mark openai unhealthy
        for _ in range(3):
            registry.mark_unhealthy("openai")
        assert registry.available_providers == ["anthropic"]


class TestFallback:
    def test_gpt4o_falls_back_to_claude(self) -> None:
        registry = _make_registry(openai="sk-test", anthropic="sk-test")
        fallbacks = registry.get_fallback_providers("gpt-4o")
        provider_names = [name for name, _ in fallbacks]
        assert "anthropic" in provider_names

    def test_fallback_skips_unavailable_providers(self) -> None:
        registry = _make_registry(openai="sk-test", anthropic="sk-test", gemini="key-test")
        # Mark anthropic unhealthy
        for _ in range(3):
            registry.mark_unhealthy("anthropic")

        fallbacks = registry.get_fallback_providers("gpt-4o")
        provider_names = [name for name, _ in fallbacks]
        assert "anthropic" not in provider_names
        assert "gemini" in provider_names

    def test_no_fallbacks_for_unknown_model(self) -> None:
        registry = _make_registry(openai="sk-test")
        assert registry.get_fallback_providers("unknown-model") == []

    def test_health_status_report(self) -> None:
        registry = _make_registry(openai="sk-test")
        registry.mark_healthy("openai", latency_ms=42)
        status = registry.get_health_status()
        assert status["openai"]["available"] is True
        assert status["openai"]["last_latency_ms"] == 42
