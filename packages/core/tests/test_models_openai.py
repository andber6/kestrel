"""Tests for OpenAI-compatible Pydantic models."""

import json

from agentrouter.models.openai import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ContentPart,
    ImageContentPart,
    ResponseFormat,
    TextContentPart,
    ToolDefinition,
)

# ---------------------------------------------------------------------------
# ChatCompletionRequest
# ---------------------------------------------------------------------------


class TestChatCompletionRequest:
    def test_minimal_request(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.model == "gpt-4o"
        assert len(req.messages) == 1
        assert req.messages[0].role == "user"
        assert req.messages[0].content == "Hello"
        assert req.stream is None
        assert req.tools is None

    def test_request_with_all_optional_fields(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.7,
            "top_p": 0.9,
            "n": 2,
            "stream": True,
            "stop": ["\n"],
            "max_tokens": 100,
            "presence_penalty": 0.5,
            "frequency_penalty": 0.3,
            "logit_bias": {"50256": -100.0},
            "logprobs": True,
            "top_logprobs": 3,
            "user": "test-user",
            "seed": 42,
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.temperature == 0.7
        assert req.stream is True
        assert req.stop == ["\n"]
        assert req.seed == 42

    def test_request_with_tools(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                            "required": ["location"],
                        },
                    },
                }
            ],
            "tool_choice": "auto",
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.tools is not None
        assert len(req.tools) == 1
        assert req.tools[0].function.name == "get_weather"
        assert req.tool_choice == "auto"

    def test_request_with_json_mode(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Return JSON"}],
            "response_format": {"type": "json_object"},
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.response_format is not None
        assert req.response_format.type == "json_object"

    def test_request_with_unknown_extra_fields(self) -> None:
        """Extra fields from newer SDK versions should be preserved, not rejected."""
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "test"}],
            "some_future_field": True,
            "another_new_param": {"nested": "value"},
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.model == "gpt-4o"
        # Extra fields are accessible
        dumped = req.model_dump()
        assert dumped["some_future_field"] is True
        assert dumped["another_new_param"] == {"nested": "value"}

    def test_request_serialization_excludes_none(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "test"}],
        }
        req = ChatCompletionRequest.model_validate(data)
        dumped = req.model_dump(exclude_none=True)
        assert "temperature" not in dumped
        assert "tools" not in dumped
        assert "model" in dumped

    def test_stop_as_single_string(self) -> None:
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "test"}],
            "stop": "\n",
        }
        req = ChatCompletionRequest.model_validate(data)
        assert req.stop == "\n"


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------


class TestChatMessage:
    def test_all_roles(self) -> None:
        for role in ("system", "user", "assistant", "tool", "developer"):
            msg = ChatMessage.model_validate({"role": role, "content": "test"})
            assert msg.role == role

    def test_message_with_tool_calls(self) -> None:
        data = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "NYC"}',
                    },
                }
            ],
        }
        msg = ChatMessage.model_validate(data)
        assert msg.tool_calls is not None
        assert msg.tool_calls[0].id == "call_abc"
        assert msg.tool_calls[0].function.name == "get_weather"

    def test_tool_result_message(self) -> None:
        data = {
            "role": "tool",
            "content": '{"temp": 72}',
            "tool_call_id": "call_abc",
        }
        msg = ChatMessage.model_validate(data)
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_abc"

    def test_multimodal_content(self) -> None:
        data = {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/img.png", "detail": "high"},
                },
            ],
        }
        msg = ChatMessage.model_validate(data)
        assert isinstance(msg.content, list)
        parts: list[ContentPart] = msg.content
        assert len(parts) == 2
        assert isinstance(parts[0], TextContentPart)
        assert parts[0].text == "What's in this image?"
        assert isinstance(parts[1], ImageContentPart)
        assert parts[1].image_url.url == "https://example.com/img.png"
        assert parts[1].image_url.detail == "high"


# ---------------------------------------------------------------------------
# ResponseFormat
# ---------------------------------------------------------------------------


class TestResponseFormat:
    def test_default_is_text(self) -> None:
        rf = ResponseFormat()
        assert rf.type == "text"

    def test_json_schema_format(self) -> None:
        data = {
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
            },
        }
        rf = ResponseFormat.model_validate(data)
        assert rf.type == "json_schema"
        assert rf.json_schema is not None


# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_with_strict(self) -> None:
        data = {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {}},
                "strict": True,
            },
        }
        tool = ToolDefinition.model_validate(data)
        assert tool.function.strict is True

    def test_tool_minimal(self) -> None:
        data = {"type": "function", "function": {"name": "noop"}}
        tool = ToolDefinition.model_validate(data)
        assert tool.function.name == "noop"
        assert tool.function.description is None
        assert tool.function.parameters is None


# ---------------------------------------------------------------------------
# ChatCompletionResponse
# ---------------------------------------------------------------------------


class TestChatCompletionResponse:
    def test_parse_full_response(self) -> None:
        data = {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "system_fingerprint": "fp_abc123",
        }
        resp = ChatCompletionResponse.model_validate(data)
        assert resp.id == "chatcmpl-abc123"
        assert resp.choices[0].message.content == "Hello!"
        assert resp.usage is not None
        assert resp.usage.total_tokens == 15

    def test_response_with_tool_calls(self) -> None:
        data = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location":"NYC"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        resp = ChatCompletionResponse.model_validate(data)
        tool_calls = resp.choices[0].message.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].function.name == "get_weather"

    def test_response_round_trip(self) -> None:
        """Serialize and re-parse should produce identical result."""
        data = {
            "id": "chatcmpl-rt",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "test"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }
        resp1 = ChatCompletionResponse.model_validate(data)
        json_str = resp1.model_dump_json()
        resp2 = ChatCompletionResponse.model_validate_json(json_str)
        assert resp1 == resp2


# ---------------------------------------------------------------------------
# Streaming models
# ---------------------------------------------------------------------------


class TestStreamingModels:
    def test_parse_role_chunk(self) -> None:
        data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
        chunk = ChatCompletionChunk.model_validate(data)
        assert chunk.choices[0].delta.role == "assistant"
        assert chunk.choices[0].delta.content is None

    def test_parse_content_chunk(self) -> None:
        data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}
            ],
        }
        chunk = ChatCompletionChunk.model_validate(data)
        assert chunk.choices[0].delta.content == "Hello"

    def test_parse_finish_chunk(self) -> None:
        data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        chunk = ChatCompletionChunk.model_validate(data)
        assert chunk.choices[0].finish_reason == "stop"

    def test_parse_chunk_with_usage(self) -> None:
        """stream_options: {include_usage: true} returns usage in the final chunk."""
        data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        chunk = ChatCompletionChunk.model_validate(data)
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 15

    def test_chunk_round_trip_json(self) -> None:
        raw = json.dumps({
            "id": "x",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}
            ],
        })
        chunk = ChatCompletionChunk.model_validate_json(raw)
        re_serialized = json.loads(chunk.model_dump_json(exclude_none=True))
        assert re_serialized["choices"][0]["delta"]["content"] == "Hi"
