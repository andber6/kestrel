"""Tests for failover cascade, backoff, and streaming error recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from kestrel.auth.api_key import AuthContext
from kestrel.config import Settings
from kestrel.models.openai import ChatCompletionRequest
from kestrel.services.proxy import ProxyService
from tests.conftest import SAMPLE_CHAT_REQUEST, SAMPLE_OPENAI_RESPONSE


def _make_proxy(settings: Settings) -> ProxyService:
    return ProxyService(
        http_client=httpx.AsyncClient(),
        settings=settings,
        log_service=None,
    )


def _dev_auth() -> AuthContext:
    return AuthContext(
        api_key_id="dev",
        provider_api_key="sk-test-key",
        provider_keys={},
    )


def _make_request() -> ChatCompletionRequest:
    return ChatCompletionRequest(**SAMPLE_CHAT_REQUEST)


class TestFailoverCascade:
    """Verify that the proxy tries fallback providers when the primary fails."""

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_failover_on_429_tries_next_provider(self, mock_backoff: AsyncMock) -> None:
        """When OpenAI returns 429, proxy should failover to Anthropic."""
        settings = Settings(
            dev_mode=True,
            dev_openai_api_key="sk-test",
            dev_anthropic_api_key="sk-ant-test",
        )
        proxy = _make_proxy(settings)

        # OpenAI returns 429
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(429, text="Rate limited")
        )
        # Anthropic returns success (translated to OpenAI format)
        anthropic_response = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello from Anthropic!"}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=anthropic_response)
        )

        request = _make_request()
        response = await proxy.proxy_request(request, _dev_auth())

        assert response.choices[0].message.content == "Hello from Anthropic!"
        # Backoff should have been called once (before second attempt)
        mock_backoff.assert_called_once_with(1)

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_failover_on_500_tries_next_provider(self, mock_backoff: AsyncMock) -> None:
        settings = Settings(
            dev_mode=True,
            dev_openai_api_key="sk-test",
            dev_anthropic_api_key="sk-ant-test",
        )
        proxy = _make_proxy(settings)

        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Internal error")
        )
        anthropic_response = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Fallback works"}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=anthropic_response)
        )

        request = _make_request()
        response = await proxy.proxy_request(request, _dev_auth())

        assert response.choices[0].message.content == "Fallback works"

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_non_retryable_error_raises_immediately(self, mock_backoff: AsyncMock) -> None:
        """401 from upstream should not trigger failover."""
        settings = Settings(
            dev_mode=True,
            dev_openai_api_key="sk-test",
            dev_anthropic_api_key="sk-ant-test",
        )
        proxy = _make_proxy(settings)

        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        request = _make_request()
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await proxy.proxy_request(request, _dev_auth())

        assert exc_info.value.response.status_code == 401
        mock_backoff.assert_not_called()

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_all_providers_fail_raises_last_error(self, mock_backoff: AsyncMock) -> None:
        """When all providers fail with retryable errors, raise the last one."""
        settings = Settings(
            dev_mode=True,
            dev_openai_api_key="sk-test",
            dev_anthropic_api_key="sk-ant-test",
        )
        proxy = _make_proxy(settings)

        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(503, text="Service unavailable")
        )
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(503, text="Also unavailable")
        )

        request = _make_request()
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await proxy.proxy_request(request, _dev_auth())

        assert exc_info.value.response.status_code == 503


class TestBackoffDelay:
    """Verify backoff delay is called with correct attempt indices."""

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_no_backoff_on_first_attempt(self, mock_backoff: AsyncMock) -> None:
        settings = Settings(dev_mode=True, dev_openai_api_key="sk-test")
        proxy = _make_proxy(settings)

        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=SAMPLE_OPENAI_RESPONSE)
        )

        request = _make_request()
        await proxy.proxy_request(request, _dev_auth())

        mock_backoff.assert_not_called()


class TestStreamingFailover:
    """Verify streaming failover behavior (before first byte only)."""

    @respx.mock
    @patch("kestrel.services.proxy._backoff_delay", new_callable=AsyncMock)
    async def test_streaming_failover_before_first_byte(self, mock_backoff: AsyncMock) -> None:
        """Streaming should failover if provider fails before sending data."""
        settings = Settings(
            dev_mode=True,
            dev_openai_api_key="sk-test",
            dev_anthropic_api_key="sk-ant-test",
        )
        proxy = _make_proxy(settings)

        # OpenAI times out
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Anthropic streams successfully
        sse_body = (
            'data: {"type":"message_start","message":{"id":"msg_1","type":"message",'
            '"role":"assistant","content":[],"model":"claude-sonnet-4-6",'
            '"stop_reason":null,"usage":{"input_tokens":10,"output_tokens":0}}}\n\n'
            'data: {"type":"content_block_start","index":0,'
            '"content_block":{"type":"text","text":""}}\n\n'
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"Hi"}}\n\n'
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
            '"usage":{"output_tokens":1}}\n\n'
            'data: {"type":"message_stop"}\n\n'
        )
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )

        request = ChatCompletionRequest(**{**SAMPLE_CHAT_REQUEST, "stream": True})
        lines = []
        async for line in proxy.proxy_stream(request, _dev_auth()):
            lines.append(line)

        # Should have received streaming data from Anthropic
        assert len(lines) > 0
        mock_backoff.assert_called_once_with(1)
