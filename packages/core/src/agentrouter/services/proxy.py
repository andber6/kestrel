"""Core proxy orchestration service."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from agentrouter.auth.api_key import AuthContext
from agentrouter.models.openai import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from agentrouter.providers.base import LLMProvider, ProviderConfig
from agentrouter.providers.openai import OpenAIProvider
from agentrouter.services.request_log import RequestLogService

logger = logging.getLogger(__name__)


class ProxyService:
    """Orchestrates request proxying, provider selection, and logging."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        log_service: RequestLogService | None = None,
        openai_base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._http_client = http_client
        self._log_service = log_service
        self._openai_base_url = openai_base_url

    def _get_provider(self, auth: AuthContext) -> LLMProvider:
        """Get the appropriate provider. Currently always OpenAI."""
        config = ProviderConfig(
            api_key=auth.provider_api_key,
            base_url=self._openai_base_url,
        )
        return OpenAIProvider(config, self._http_client)

    async def proxy_request(
        self,
        request: ChatCompletionRequest,
        auth: AuthContext,
    ) -> ChatCompletionResponse:
        """Proxy a non-streaming chat completion request."""
        provider = self._get_provider(auth)
        start = time.monotonic()

        try:
            response = await provider.chat_completion(request)
        except httpx.HTTPStatusError as exc:
            self._fire_log(
                auth=auth,
                request=request,
                error=str(exc),
                status_code=exc.response.status_code,
                latency_ms=_elapsed_ms(start),
            )
            raise
        except Exception as exc:
            self._fire_log(
                auth=auth,
                request=request,
                error=str(exc),
                latency_ms=_elapsed_ms(start),
            )
            raise

        latency_ms = _elapsed_ms(start)
        usage = response.usage
        self._fire_log(
            auth=auth,
            request=request,
            response_dict=response.model_dump(),
            finish_reason=(response.choices[0].finish_reason if response.choices else None),
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            latency_ms=latency_ms,
        )
        return response

    async def proxy_stream(
        self,
        request: ChatCompletionRequest,
        auth: AuthContext,
    ) -> AsyncGenerator[str, None]:
        """Proxy a streaming chat completion request. Yields raw SSE lines."""
        provider = self._get_provider(auth)
        start = time.monotonic()
        first_token_time: float | None = None
        chunks: list[ChatCompletionChunk] = []

        try:
            async for line in provider.chat_completion_stream(request):
                if first_token_time is None:
                    first_token_time = time.monotonic()

                # Parse for logging, forward raw
                data_str = line.strip()
                if data_str.startswith("data: ") and data_str[6:].strip() != "[DONE]":
                    try:
                        chunk = ChatCompletionChunk.model_validate_json(data_str[6:])
                        chunks.append(chunk)
                    except Exception:
                        pass  # Forward even if we can't parse for logging

                yield line
        except Exception as exc:
            self._fire_log(
                auth=auth,
                request=request,
                is_streaming=True,
                error=str(exc),
                latency_ms=_elapsed_ms(start),
            )
            raise

        # After stream completes, log asynchronously
        latency_ms = _elapsed_ms(start)
        ttft_ms = int((first_token_time - start) * 1000) if first_token_time else None
        assembled = _assemble_chunks(chunks)
        self._fire_log(
            auth=auth,
            request=request,
            is_streaming=True,
            response_dict=assembled.get("response"),
            finish_reason=assembled.get("finish_reason"),
            prompt_tokens=assembled.get("prompt_tokens"),
            completion_tokens=assembled.get("completion_tokens"),
            total_tokens=assembled.get("total_tokens"),
            latency_ms=latency_ms,
            time_to_first_token_ms=ttft_ms,
        )

    def _fire_log(
        self,
        *,
        auth: AuthContext,
        request: ChatCompletionRequest,
        is_streaming: bool = False,
        response_dict: dict[str, Any] | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
        error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Fire-and-forget log write."""
        if self._log_service is None:
            return

        messages_raw = [m.model_dump(exclude_none=True) for m in request.messages]
        has_tools = request.tools is not None and len(request.tools) > 0
        has_json_mode = (
            request.response_format is not None and request.response_format.type != "text"
        )

        asyncio.create_task(
            self._log_service.log(
                api_key_id=auth.api_key_id,
                model_requested=request.model,
                model_used=request.model,  # Same for now; routing changes this later
                messages=messages_raw,
                is_streaming=is_streaming,
                has_tools=has_tools,
                has_json_mode=has_json_mode,
                response=response_dict,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                time_to_first_token_ms=time_to_first_token_ms,
                error=error,
                status_code=status_code,
            )
        )


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _assemble_chunks(chunks: list[ChatCompletionChunk]) -> dict[str, Any]:
    """Assemble streaming chunks into a summary for logging."""
    if not chunks:
        return {}

    content_parts: list[str] = []
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    for chunk in chunks:
        for choice in chunk.choices:
            if choice.delta.content:
                content_parts.append(choice.delta.content)
            if choice.finish_reason:
                finish_reason = choice.finish_reason
        if chunk.usage:
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
            total_tokens = chunk.usage.total_tokens

    return {
        "response": {"content": "".join(content_parts)} if content_parts else None,
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
