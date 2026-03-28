"""Integration tests for /v1/chat/completions endpoint."""

from __future__ import annotations

import httpx
import respx

from tests.conftest import SAMPLE_CHAT_REQUEST, SAMPLE_OPENAI_RESPONSE


class TestNonStreamingProxy:
    @respx.mock
    async def test_proxies_request_to_openai(self, client: httpx.AsyncClient) -> None:
        """Full round-trip: client → AgentRouter → mocked OpenAI → client."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=SAMPLE_OPENAI_RESPONSE)
        )

        response = await client.post("/v1/chat/completions", json=SAMPLE_CHAT_REQUEST)

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "chatcmpl-test123"
        assert body["choices"][0]["message"]["content"] == "Hello! How can I help you?"
        assert body["usage"]["total_tokens"] == 19

    @respx.mock
    async def test_response_includes_request_id_header(
        self, client: httpx.AsyncClient
    ) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=SAMPLE_OPENAI_RESPONSE)
        )

        response = await client.post("/v1/chat/completions", json=SAMPLE_CHAT_REQUEST)

        assert "x-request-id" in response.headers
        assert "x-response-time-ms" in response.headers

    @respx.mock
    async def test_proxies_request_with_tools(self, client: httpx.AsyncClient) -> None:
        tool_response = {
            **SAMPLE_OPENAI_RESPONSE,
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
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=tool_response)
        )

        request_data = {
            **SAMPLE_CHAT_REQUEST,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }
        response = await client.post("/v1/chat/completions", json=request_data)

        assert response.status_code == 200
        body = response.json()
        assert body["choices"][0]["finish_reason"] == "tool_calls"
        assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"

    @respx.mock
    async def test_forwards_unknown_request_fields(
        self, client: httpx.AsyncClient
    ) -> None:
        """Extra fields from newer SDKs should be forwarded to the provider."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=SAMPLE_OPENAI_RESPONSE)
        )

        request_data = {
            **SAMPLE_CHAT_REQUEST,
            "future_param": True,
        }
        response = await client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 200


class TestErrorHandling:
    @respx.mock
    async def test_upstream_500_returns_error(self, client: httpx.AsyncClient) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        response = await client.post("/v1/chat/completions", json=SAMPLE_CHAT_REQUEST)
        assert response.status_code == 500

    @respx.mock
    async def test_upstream_429_returns_rate_limit(
        self, client: httpx.AsyncClient
    ) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(429, text="Rate limit exceeded")
        )

        response = await client.post("/v1/chat/completions", json=SAMPLE_CHAT_REQUEST)
        assert response.status_code == 429

    async def test_invalid_request_body(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/v1/chat/completions",
            json={"not_a_valid": "request"},
        )
        assert response.status_code == 422

    async def test_missing_messages(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o"},
        )
        assert response.status_code == 422


class TestHealthCheck:
    async def test_health_endpoint(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
