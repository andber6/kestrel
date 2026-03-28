"""Tests for Mistral provider translation."""

from __future__ import annotations

import httpx

from kestrel.models.openai import ChatCompletionRequest
from kestrel.providers.mistral import MistralProvider


def _make_provider() -> MistralProvider:
    return MistralProvider(api_key="test-key", http_client=httpx.AsyncClient())


class TestMistralTranslation:
    def test_strips_unsupported_fields(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": "hi"}],
                "logprobs": True,
                "top_logprobs": 3,
                "logit_bias": {"123": 1.0},
                "temperature": 0.5,
            }
        )
        body = _make_provider().translate_request(req)
        assert "logprobs" not in body
        assert "top_logprobs" not in body
        assert "logit_bias" not in body
        assert body["temperature"] == 0.5

    def test_preserves_tools(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": "search"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {"name": "search", "parameters": {"type": "object"}},
                    }
                ],
            }
        )
        body = _make_provider().translate_request(req)
        assert len(body["tools"]) == 1

    def test_standard_request_passthrough(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": "Be helpful."},
                    {"role": "user", "content": "Hello"},
                ],
                "max_tokens": 200,
            }
        )
        body = _make_provider().translate_request(req)
        assert body["model"] == "mistral-small-latest"
        assert len(body["messages"]) == 2
        assert body["max_tokens"] == 200

    def test_provider_name(self) -> None:
        assert _make_provider().name == "mistral"
