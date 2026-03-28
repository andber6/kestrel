"""Tests for SSE streaming proxy."""

from __future__ import annotations

import httpx
import respx

from tests.conftest import SAMPLE_CHAT_REQUEST


def _make_sse_response(*chunks: str) -> str:
    """Build an SSE response body from data strings."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {chunk}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines)


CHUNK_ROLE = (
    '{"id":"chatcmpl-s1","object":"chat.completion.chunk","created":1,'
    '"model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant"},'
    '"finish_reason":null}]}'
)

CHUNK_CONTENT_1 = (
    '{"id":"chatcmpl-s1","object":"chat.completion.chunk","created":1,'
    '"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"Hello"},'
    '"finish_reason":null}]}'
)

CHUNK_CONTENT_2 = (
    '{"id":"chatcmpl-s1","object":"chat.completion.chunk","created":1,'
    '"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"!"},'
    '"finish_reason":null}]}'
)

CHUNK_FINISH = (
    '{"id":"chatcmpl-s1","object":"chat.completion.chunk","created":1,'
    '"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'
)


class TestStreamingProxy:
    @respx.mock
    async def test_streams_chunks_to_client(self, client: httpx.AsyncClient) -> None:
        """Verify that SSE chunks from upstream are forwarded."""
        sse_body = _make_sse_response(CHUNK_ROLE, CHUNK_CONTENT_1, CHUNK_CONTENT_2, CHUNK_FINISH)
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )

        request_data = {**SAMPLE_CHAT_REQUEST, "stream": True}
        response = await client.post("/v1/chat/completions", json=request_data)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        # Parse SSE lines
        text = response.text
        data_lines = [line for line in text.split("\n") if line.startswith("data: ")]

        # Should have: role chunk, 2 content chunks, finish chunk, [DONE]
        assert len(data_lines) == 5
        assert data_lines[-1] == "data: [DONE]"

        # Verify content chunks contain expected text
        assert '"content":"Hello"' in data_lines[1]
        assert '"content":"!"' in data_lines[2]

    @respx.mock
    async def test_streaming_response_headers(self, client: httpx.AsyncClient) -> None:
        sse_body = _make_sse_response(CHUNK_ROLE, CHUNK_FINISH)
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )

        request_data = {**SAMPLE_CHAT_REQUEST, "stream": True}
        response = await client.post("/v1/chat/completions", json=request_data)

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"

    @respx.mock
    async def test_non_stream_request_returns_json(self, client: httpx.AsyncClient) -> None:
        """When stream is False/None, should return regular JSON."""
        from tests.conftest import SAMPLE_OPENAI_RESPONSE

        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=SAMPLE_OPENAI_RESPONSE)
        )

        response = await client.post("/v1/chat/completions", json=SAMPLE_CHAT_REQUEST)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["object"] == "chat.completion"
