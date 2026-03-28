"""Tests for Groq provider translation."""

from __future__ import annotations

from agentrouter.models.openai import ChatCompletionRequest
from agentrouter.providers.groq import GroqProvider


def _make_provider() -> GroqProvider:
    """Create a GroqProvider for translation testing (no HTTP calls)."""
    import httpx

    return GroqProvider(
        api_key="test-key",
        http_client=httpx.AsyncClient(),
    )


class TestGroqTranslation:
    def test_strips_unsupported_fields(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "hi"}],
                "logprobs": True,
                "top_logprobs": 3,
                "logit_bias": {"123": 1.0},
                "temperature": 0.5,
            }
        )
        provider = _make_provider()
        body = provider.translate_request(req)

        assert "logprobs" not in body
        assert "top_logprobs" not in body
        assert "logit_bias" not in body
        # Supported fields preserved
        assert body["temperature"] == 0.5
        assert body["model"] == "llama-3.1-8b-instant"

    def test_downgrades_json_schema_to_json_object(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "test", "schema": {"type": "object"}},
                },
            }
        )
        provider = _make_provider()
        body = provider.translate_request(req)

        assert body["response_format"] == {"type": "json_object"}

    def test_preserves_json_object_format(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {"type": "json_object"},
            }
        )
        provider = _make_provider()
        body = provider.translate_request(req)

        assert body["response_format"] == {"type": "json_object"}

    def test_passthrough_for_standard_request(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "llama-3.1-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello"},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            }
        )
        provider = _make_provider()
        body = provider.translate_request(req)

        assert body["model"] == "llama-3.1-70b-versatile"
        assert len(body["messages"]) == 2
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 500
