"""Shared base for OpenAI-compatible providers (OpenAI, Groq, etc.)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx

from agentrouter.models.openai import ChatCompletionRequest, ChatCompletionResponse
from agentrouter.providers.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Base class for providers that use the OpenAI API format.

    OpenAI, Groq, Together AI, and others use the same request/response
    format and SSE streaming protocol. This base class handles the HTTP
    mechanics; subclasses only need to override translation methods if
    they need to strip or modify certain fields.
    """

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        http_client: httpx.AsyncClient,
        timeout_connect: float = 5.0,
        timeout_read: float = 120.0,
    ) -> None:
        self._name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client
        self._timeout_connect = timeout_connect
        self._timeout_read = timeout_read

    @property
    def name(self) -> str:
        return self._name

    def _completions_url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._timeout_connect,
            read=self._timeout_read,
            write=5.0,
            pool=5.0,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """Default: OpenAI format is native."""
        return request.model_dump(exclude_none=True)

    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        """Default: OpenAI format is native."""
        return ChatCompletionResponse.model_validate(raw)

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        body = self.translate_request(request)
        body.pop("stream", None)

        response = await self._http_client.post(
            self._completions_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        )
        response.raise_for_status()
        return self.translate_response(response.json())

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        body = self.translate_request(request)
        body["stream"] = True

        async with self._http_client.stream(
            "POST",
            self._completions_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                yield f"{line}\n\n"
