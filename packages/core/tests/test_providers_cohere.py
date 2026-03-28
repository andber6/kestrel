"""Tests for Cohere provider translation."""

from __future__ import annotations

import httpx

from kestrel.models.openai import ChatCompletionRequest
from kestrel.providers.cohere import CohereProvider


def _make_provider() -> CohereProvider:
    return CohereProvider(api_key="test-key", http_client=httpx.AsyncClient())


class TestCohereRequestTranslation:
    def test_basic_message(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [{"role": "user", "content": "Hello"}],
            }
        )
        body = _make_provider().translate_request(req)
        assert body["model"] == "command-r-plus"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == "Hello"

    def test_system_message_preserved(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [
                    {"role": "system", "content": "Be helpful."},
                    {"role": "user", "content": "Hi"},
                ],
            }
        )
        body = _make_provider().translate_request(req)
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "Be helpful."

    def test_temperature_and_top_p(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": 0.5,
                "top_p": 0.8,
            }
        )
        body = _make_provider().translate_request(req)
        assert body["temperature"] == 0.5
        assert body["p"] == 0.8

    def test_stop_sequences(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [{"role": "user", "content": "Hi"}],
                "stop": ["END"],
            }
        )
        body = _make_provider().translate_request(req)
        assert body["stop_sequences"] == ["END"]

    def test_tool_definitions(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [{"role": "user", "content": "Search"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search",
                            "description": "Search the web",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            }
        )
        body = _make_provider().translate_request(req)
        assert len(body["tools"]) == 1
        assert body["tools"][0]["function"]["name"] == "search"

    def test_tool_calls_in_assistant_message(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "command-r-plus",
                "messages": [
                    {"role": "user", "content": "Search cats"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": '{"q":"cats"}'},
                            }
                        ],
                    },
                    {"role": "tool", "content": "results", "tool_call_id": "call_1"},
                ],
            }
        )
        body = _make_provider().translate_request(req)
        assert body["messages"][1]["tool_calls"][0]["id"] == "call_1"
        assert body["messages"][2]["role"] == "tool"
        assert body["messages"][2]["tool_call_id"] == "call_1"


class TestCohereResponseTranslation:
    def test_basic_text_response(self) -> None:
        raw = {
            "id": "abc123",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello!"}],
            },
            "finish_reason": "COMPLETE",
            "model": "command-r-plus",
            "usage": {
                "billed_units": {"input_tokens": 5, "output_tokens": 3},
                "tokens": {"input_tokens": 5, "output_tokens": 3},
            },
        }
        resp = _make_provider().translate_response(raw)
        assert resp.choices[0].message.content == "Hello!"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage is not None
        assert resp.usage.prompt_tokens == 5
        assert resp.usage.completion_tokens == 3

    def test_tool_call_response(self) -> None:
        raw = {
            "id": "xyz",
            "message": {
                "role": "assistant",
                "content": [],
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"q":"cats"}'},
                    }
                ],
            },
            "finish_reason": "TOOL_CALL",
            "model": "command-r-plus",
            "usage": {
                "billed_units": {"input_tokens": 10, "output_tokens": 5},
                "tokens": {"input_tokens": 10, "output_tokens": 5},
            },
        }
        resp = _make_provider().translate_response(raw)
        assert resp.choices[0].finish_reason == "tool_calls"
        tc = resp.choices[0].message.tool_calls
        assert tc is not None
        assert tc[0].function.name == "search"

    def test_max_tokens_finish(self) -> None:
        raw = {
            "id": "abc",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "trunc"}]},
            "finish_reason": "MAX_TOKENS",
            "model": "command-r-plus",
            "usage": {"billed_units": {"input_tokens": 1, "output_tokens": 1}},
        }
        resp = _make_provider().translate_response(raw)
        assert resp.choices[0].finish_reason == "length"

    def test_response_has_openai_format(self) -> None:
        raw = {
            "id": "abc",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
            "finish_reason": "COMPLETE",
            "model": "command-r-plus",
            "usage": {"billed_units": {"input_tokens": 1, "output_tokens": 1}},
        }
        resp = _make_provider().translate_response(raw)
        assert resp.object == "chat.completion"
        assert resp.id.startswith("chatcmpl-")

    def test_provider_name(self) -> None:
        assert _make_provider().name == "cohere"
