"""Tests for Anthropic provider translation."""

from __future__ import annotations

import json

import httpx

from agentrouter.models.openai import ChatCompletionRequest
from agentrouter.providers.anthropic import AnthropicProvider


def _make_provider() -> AnthropicProvider:
    return AnthropicProvider(api_key="test-key", http_client=httpx.AsyncClient())


# ---------------------------------------------------------------------------
# Request translation: OpenAI → Anthropic
# ---------------------------------------------------------------------------


class TestRequestTranslation:
    def test_basic_message(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hello"}],
        })
        body = _make_provider().translate_request(req)

        assert body["model"] == "claude-sonnet-4-6"
        assert body["max_tokens"] == 4096  # default
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == [{"type": "text", "text": "Hello"}]
        assert "system" not in body

    def test_system_message_extracted(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"},
            ],
        })
        body = _make_provider().translate_request(req)

        assert body["system"] == "You are helpful."
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"

    def test_multiple_system_messages_merged(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "system", "content": "Rule 1"},
                {"role": "system", "content": "Rule 2"},
                {"role": "user", "content": "Go"},
            ],
        })
        body = _make_provider().translate_request(req)

        assert body["system"] == "Rule 1\n\nRule 2"

    def test_developer_role_becomes_system(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "developer", "content": "Developer instructions"},
                {"role": "user", "content": "Hi"},
            ],
        })
        body = _make_provider().translate_request(req)

        assert body["system"] == "Developer instructions"

    def test_max_tokens_forwarded(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 500,
        })
        body = _make_provider().translate_request(req)
        assert body["max_tokens"] == 500

    def test_temperature_and_top_p(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.7,
            "top_p": 0.9,
        })
        body = _make_provider().translate_request(req)
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.9

    def test_stop_sequences(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "stop": ["END", "STOP"],
        })
        body = _make_provider().translate_request(req)
        assert body["stop_sequences"] == ["END", "STOP"]

    def test_stop_single_string(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "stop": "\n",
        })
        body = _make_provider().translate_request(req)
        assert body["stop_sequences"] == ["\n"]

    def test_tool_definitions(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Weather?"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                },
            }],
        })
        body = _make_provider().translate_request(req)

        assert len(body["tools"]) == 1
        assert body["tools"][0]["name"] == "get_weather"
        assert body["tools"][0]["description"] == "Get weather for a location"
        assert "input_schema" in body["tools"][0]

    def test_assistant_tool_calls_become_tool_use(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "user", "content": "Weather?"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "NYC"}',
                        },
                    }],
                },
                {
                    "role": "tool",
                    "content": '{"temp": 72}',
                    "tool_call_id": "call_1",
                },
            ],
        })
        body = _make_provider().translate_request(req)

        # Assistant message should have tool_use block
        assistant_msg = body["messages"][1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"][0]["type"] == "tool_use"
        assert assistant_msg["content"][0]["id"] == "call_1"
        assert assistant_msg["content"][0]["input"] == {"city": "NYC"}

        # Tool result should be in a user message
        tool_msg = body["messages"][2]
        assert tool_msg["role"] == "user"
        assert tool_msg["content"][0]["type"] == "tool_result"
        assert tool_msg["content"][0]["tool_use_id"] == "call_1"

    def test_consecutive_tool_results_merged(self) -> None:
        req = ChatCompletionRequest.model_validate({
            "model": "claude-sonnet-4-6",
            "messages": [
                {"role": "user", "content": "Get weather and time"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": "{}",
                            },
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "get_time",
                                "arguments": "{}",
                            },
                        },
                    ],
                },
                {"role": "tool", "content": "72F", "tool_call_id": "call_1"},
                {"role": "tool", "content": "3pm", "tool_call_id": "call_2"},
            ],
        })
        body = _make_provider().translate_request(req)

        # Two tool results should be merged into one user message
        tool_msg = body["messages"][2]
        assert tool_msg["role"] == "user"
        assert len(tool_msg["content"]) == 2
        assert tool_msg["content"][0]["tool_use_id"] == "call_1"
        assert tool_msg["content"][1]["tool_use_id"] == "call_2"


# ---------------------------------------------------------------------------
# Response translation: Anthropic → OpenAI
# ---------------------------------------------------------------------------


class TestResponseTranslation:
    def test_basic_text_response(self) -> None:
        raw = {
            "id": "msg_abc",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        resp = _make_provider().translate_response(raw)

        assert resp.choices[0].message.content == "Hello!"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.model == "claude-sonnet-4-6"
        assert resp.usage is not None
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 5
        assert resp.usage.total_tokens == 15

    def test_tool_use_response(self) -> None:
        raw = {
            "id": "msg_xyz",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {"city": "NYC"},
                }
            ],
            "model": "claude-sonnet-4-6",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }
        resp = _make_provider().translate_response(raw)

        assert resp.choices[0].finish_reason == "tool_calls"
        tool_calls = resp.choices[0].message.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].id == "toolu_1"
        assert tool_calls[0].function.name == "get_weather"
        assert json.loads(tool_calls[0].function.arguments) == {"city": "NYC"}

    def test_max_tokens_stop_reason(self) -> None:
        raw = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Truncated..."}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 10, "output_tokens": 100},
        }
        resp = _make_provider().translate_response(raw)
        assert resp.choices[0].finish_reason == "length"

    def test_response_has_openai_format(self) -> None:
        raw = {
            "id": "msg_abc",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "test"}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        resp = _make_provider().translate_response(raw)

        assert resp.object == "chat.completion"
        assert resp.id.startswith("chatcmpl-")
        assert resp.created > 0
