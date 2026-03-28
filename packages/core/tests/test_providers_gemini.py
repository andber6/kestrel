"""Tests for Gemini provider translation."""

from __future__ import annotations

import json

import httpx

from agentrouter.models.openai import ChatCompletionRequest
from agentrouter.providers.gemini import GeminiProvider


def _make_provider() -> GeminiProvider:
    return GeminiProvider(api_key="test-key", http_client=httpx.AsyncClient())


# ---------------------------------------------------------------------------
# Request translation: OpenAI → Gemini
# ---------------------------------------------------------------------------


class TestRequestTranslation:
    def test_basic_message(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [{"role": "user", "content": "Hello"}],
            }
        )
        body = _make_provider().translate_request(req)

        assert len(body["contents"]) == 1
        assert body["contents"][0]["role"] == "user"
        assert body["contents"][0]["parts"] == [{"text": "Hello"}]

    def test_system_message_to_system_instruction(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [
                    {"role": "system", "content": "Be concise"},
                    {"role": "user", "content": "Hi"},
                ],
            }
        )
        body = _make_provider().translate_request(req)

        assert "systemInstruction" in body
        assert body["systemInstruction"]["parts"] == [{"text": "Be concise"}]
        assert len(body["contents"]) == 1

    def test_assistant_becomes_model_role(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                    {"role": "user", "content": "How are you?"},
                ],
            }
        )
        body = _make_provider().translate_request(req)

        assert body["contents"][0]["role"] == "user"
        assert body["contents"][1]["role"] == "model"
        assert body["contents"][1]["parts"] == [{"text": "Hello!"}]
        assert body["contents"][2]["role"] == "user"

    def test_generation_config(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": 0.5,
                "top_p": 0.8,
                "max_tokens": 200,
                "stop": ["END"],
            }
        )
        body = _make_provider().translate_request(req)

        gc = body["generationConfig"]
        assert gc["temperature"] == 0.5
        assert gc["topP"] == 0.8
        assert gc["maxOutputTokens"] == 200
        assert gc["stopSequences"] == ["END"]

    def test_json_mode(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [{"role": "user", "content": "JSON please"}],
                "response_format": {"type": "json_object"},
            }
        )
        body = _make_provider().translate_request(req)
        assert body["generationConfig"]["responseMimeType"] == "application/json"

    def test_tool_definitions(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [{"role": "user", "content": "Search"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search",
                            "description": "Search the web",
                            "parameters": {
                                "type": "object",
                                "properties": {"query": {"type": "string"}},
                            },
                        },
                    }
                ],
            }
        )
        body = _make_provider().translate_request(req)

        decls = body["tools"][0]["functionDeclarations"]
        assert len(decls) == 1
        assert decls[0]["name"] == "search"

    def test_tool_calls_become_function_call(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gemini-1.5-flash",
                "messages": [
                    {"role": "user", "content": "Search for cats"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "cats"}',
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "content": '{"results": ["cat1"]}',
                        "tool_call_id": "call_1",
                    },
                ],
            }
        )
        body = _make_provider().translate_request(req)

        # Assistant message should have functionCall
        model_msg = body["contents"][1]
        assert model_msg["role"] == "model"
        assert "functionCall" in model_msg["parts"][0]

        # Tool result should be functionResponse in user message
        user_msg = body["contents"][2]
        assert user_msg["role"] == "user"
        assert "functionResponse" in user_msg["parts"][0]


# ---------------------------------------------------------------------------
# Response translation: Gemini → OpenAI
# ---------------------------------------------------------------------------


class TestResponseTranslation:
    def test_basic_text_response(self) -> None:
        raw = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello!"}], "role": "model"},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 3,
                "totalTokenCount": 8,
            },
            "modelVersion": "gemini-1.5-flash",
        }
        resp = _make_provider().translate_response(raw)

        assert resp.choices[0].message.content == "Hello!"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage is not None
        assert resp.usage.prompt_tokens == 5
        assert resp.usage.total_tokens == 8

    def test_function_call_response(self) -> None:
        raw = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "search",
                                    "args": {"query": "cats"},
                                }
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
        resp = _make_provider().translate_response(raw)

        tool_calls = resp.choices[0].message.tool_calls
        assert tool_calls is not None
        assert tool_calls[0].function.name == "search"
        assert json.loads(tool_calls[0].function.arguments) == {"query": "cats"}

    def test_safety_finish_reason(self) -> None:
        raw = {
            "candidates": [
                {
                    "content": {"parts": [{"text": ""}], "role": "model"},
                    "finishReason": "SAFETY",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 0,
                "totalTokenCount": 5,
            },
        }
        resp = _make_provider().translate_response(raw)
        assert resp.choices[0].finish_reason == "content_filter"

    def test_response_has_openai_format(self) -> None:
        raw = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "test"}], "role": "model"},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1,
                "candidatesTokenCount": 1,
                "totalTokenCount": 2,
            },
        }
        resp = _make_provider().translate_response(raw)

        assert resp.object == "chat.completion"
        assert resp.id.startswith("chatcmpl-")
