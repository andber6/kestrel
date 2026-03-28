"""Core proxy orchestration service with failover."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from agentrouter.auth.api_key import AuthContext
from agentrouter.config import Settings
from agentrouter.models.openai import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from agentrouter.providers.base import LLMProvider
from agentrouter.services.provider_registry import ProviderRegistry
from agentrouter.services.request_log import RequestLogService

logger = logging.getLogger(__name__)

# HTTP status codes that trigger failover
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2


class ProxyService:
    """Orchestrates request proxying, provider selection, and logging."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        settings: Settings,
        log_service: RequestLogService | None = None,
    ) -> None:
        self._http_client = http_client
        self._settings = settings
        self._log_service = log_service

    def _build_registry(self, auth: AuthContext) -> ProviderRegistry:
        """Build a provider registry with the operator's API keys."""
        # In dev mode, use dev keys from settings
        if self._settings.dev_mode:
            keys = {
                "openai": auth.provider_api_key or self._settings.dev_openai_api_key,
                "anthropic": self._settings.dev_anthropic_api_key,
                "gemini": self._settings.dev_gemini_api_key,
                "groq": self._settings.dev_groq_api_key,
            }
        else:
            # In production, the primary key comes from auth context.
            # Additional provider keys would come from the operator's stored credentials.
            keys = {"openai": auth.provider_api_key}

        # Filter out empty keys
        keys = {k: v for k, v in keys.items() if v}

        return ProviderRegistry.from_settings(
            self._settings,
            self._http_client,
            provider_api_keys=keys,
        )

    def _get_provider_and_model(
        self, registry: ProviderRegistry, model: str
    ) -> tuple[LLMProvider, str] | None:
        """Resolve provider for a model. Returns (provider, model) or None."""
        provider = registry.get_provider_for_model(model)
        if provider and registry.is_healthy(provider.name):
            return provider, model
        return None

    async def proxy_request(
        self,
        request: ChatCompletionRequest,
        auth: AuthContext,
    ) -> ChatCompletionResponse:
        """Proxy a non-streaming chat completion request with failover."""
        registry = self._build_registry(auth)
        start = time.monotonic()

        # Build list of (provider, model) to try
        attempts = self._build_attempt_list(registry, request.model)

        last_error: Exception | None = None
        for provider, model_name in attempts:
            try:
                # Override model in request for this attempt
                attempt_request = request.model_copy(update={"model": model_name})
                response = await provider.chat_completion(attempt_request)

                latency_ms = _elapsed_ms(start)
                registry.mark_healthy(provider.name, latency_ms)

                usage = response.usage
                self._fire_log(
                    auth=auth,
                    request=request,
                    model_used=model_name,
                    provider_used=provider.name,
                    response_dict=response.model_dump(),
                    finish_reason=(
                        response.choices[0].finish_reason if response.choices else None
                    ),
                    prompt_tokens=usage.prompt_tokens if usage else None,
                    completion_tokens=usage.completion_tokens if usage else None,
                    total_tokens=usage.total_tokens if usage else None,
                    latency_ms=latency_ms,
                )
                return response

            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in _RETRYABLE_STATUS_CODES:
                    registry.mark_unhealthy(provider.name)
                    logger.warning(
                        "Provider %s returned %s for model %s, trying failover",
                        provider.name,
                        exc.response.status_code,
                        model_name,
                    )
                    continue
                # Non-retryable error (400, 401, 403, etc.)
                self._fire_log(
                    auth=auth,
                    request=request,
                    model_used=model_name,
                    provider_used=provider.name,
                    error=str(exc),
                    status_code=exc.response.status_code,
                    latency_ms=_elapsed_ms(start),
                )
                raise

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                registry.mark_unhealthy(provider.name)
                logger.warning(
                    "Provider %s timed out for model %s, trying failover",
                    provider.name,
                    model_name,
                )
                continue

        # All attempts failed
        self._fire_log(
            auth=auth,
            request=request,
            model_used=request.model,
            provider_used="none",
            error=str(last_error) if last_error else "No available provider",
            latency_ms=_elapsed_ms(start),
        )
        if last_error:
            raise last_error
        raise RuntimeError(f"No provider available for model: {request.model}")

    async def proxy_stream(
        self,
        request: ChatCompletionRequest,
        auth: AuthContext,
    ) -> AsyncGenerator[str, None]:
        """Proxy a streaming request. Failover only before first byte."""
        registry = self._build_registry(auth)
        start = time.monotonic()
        attempts = self._build_attempt_list(registry, request.model)

        last_error: Exception | None = None
        for provider, model_name in attempts:
            try:
                attempt_request = request.model_copy(update={"model": model_name})
                first_token_time: float | None = None
                chunks: list[ChatCompletionChunk] = []

                async for line in provider.chat_completion_stream(attempt_request):
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                        registry.mark_healthy(
                            provider.name, _elapsed_ms(start)
                        )

                    # Parse for logging, forward raw
                    data_str = line.strip()
                    if data_str.startswith("data: ") and data_str[6:].strip() != "[DONE]":
                        try:
                            chunk = ChatCompletionChunk.model_validate_json(data_str[6:])
                            chunks.append(chunk)
                        except Exception:
                            pass

                    yield line

                # Stream completed successfully
                latency_ms = _elapsed_ms(start)
                ttft_ms = (
                    int((first_token_time - start) * 1000) if first_token_time else None
                )
                assembled = _assemble_chunks(chunks)
                self._fire_log(
                    auth=auth,
                    request=request,
                    model_used=model_name,
                    provider_used=provider.name,
                    is_streaming=True,
                    response_dict=assembled.get("response"),
                    finish_reason=assembled.get("finish_reason"),
                    prompt_tokens=assembled.get("prompt_tokens"),
                    completion_tokens=assembled.get("completion_tokens"),
                    total_tokens=assembled.get("total_tokens"),
                    latency_ms=latency_ms,
                    time_to_first_token_ms=ttft_ms,
                )
                return  # Success

            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                registry.mark_unhealthy(provider.name)
                logger.warning(
                    "Provider %s failed for streaming model %s, trying failover",
                    provider.name,
                    model_name,
                )
                continue

        # All attempts failed
        if last_error:
            raise last_error
        raise RuntimeError(f"No provider available for model: {request.model}")

    def _build_attempt_list(
        self, registry: ProviderRegistry, model: str
    ) -> list[tuple[LLMProvider, str]]:
        """Build ordered list of (provider, model) to try."""
        attempts: list[tuple[LLMProvider, str]] = []

        # Primary
        primary = self._get_provider_and_model(registry, model)
        if primary:
            attempts.append(primary)

        # Fallbacks (up to MAX_RETRIES)
        for provider_name, alt_model in registry.get_fallback_providers(model):
            if len(attempts) > _MAX_RETRIES:
                break
            provider = registry.get_provider(provider_name)
            if provider:
                attempts.append((provider, alt_model))

        # If no primary found but fallbacks exist, use them
        if not attempts:
            # Last resort: try any available provider with the original model
            for name in registry.available_providers:
                provider = registry.get_provider(name)
                if provider:
                    attempts.append((provider, model))
                    break

        return attempts

    def _fire_log(
        self,
        *,
        auth: AuthContext,
        request: ChatCompletionRequest,
        model_used: str = "",
        provider_used: str = "",
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
                model_used=model_used or request.model,
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
