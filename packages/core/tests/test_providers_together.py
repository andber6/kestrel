"""Tests for Together AI provider translation."""

from __future__ import annotations

import httpx

from agentrouter.models.openai import ChatCompletionRequest
from agentrouter.providers.together import TogetherProvider


def _make_provider() -> TogetherProvider:
    return TogetherProvider(api_key="test-key", http_client=httpx.AsyncClient())


class TestTogetherTranslation:
    def test_strips_unsupported_fields(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "messages": [{"role": "user", "content": "hi"}],
                "logit_bias": {"123": 1.0},
                "top_logprobs": 5,
                "temperature": 0.7,
            }
        )
        body = _make_provider().translate_request(req)
        assert "logit_bias" not in body
        assert "top_logprobs" not in body
        assert body["temperature"] == 0.7

    def test_downgrades_json_schema(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "messages": [{"role": "user", "content": "json"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "test", "schema": {"type": "object"}},
                },
            }
        )
        body = _make_provider().translate_request(req)
        assert body["response_format"] == {"type": "json_object"}

    def test_standard_request_passthrough(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 500,
            }
        )
        body = _make_provider().translate_request(req)
        assert body["max_tokens"] == 500

    def test_provider_name(self) -> None:
        assert _make_provider().name == "together"
