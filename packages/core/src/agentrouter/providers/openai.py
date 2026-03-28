"""OpenAI provider adapter — pass-through implementation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx

from agentrouter.models.openai import ChatCompletionRequest, ChatCompletionResponse
from agentrouter.providers.base import LLMProvider, ProviderConfig


class OpenAIProvider(LLMProvider):
    """Pass-through adapter for the OpenAI API."""

    def __init__(self, config: ProviderConfig, http_client: httpx.AsyncClient) -> None:
        super().__init__(config, http_client)
        self._completions_url = f"{config.base_url.rstrip('/')}/chat/completions"

    @property
    def name(self) -> str:
        return "openai"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.config.timeout_connect,
            read=self.config.timeout_read,
            write=5.0,
            pool=5.0,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """OpenAI format is native — no translation needed."""
        return request.model_dump(exclude_none=True)

    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        """OpenAI format is native — no translation needed."""
        return ChatCompletionResponse.model_validate(raw)

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        body = self.translate_request(request)
        body.pop("stream", None)

        response = await self.http_client.post(
            self._completions_url,
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

        async with self.http_client.stream(
            "POST",
            self._completions_url,
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                # Forward raw SSE lines
                yield f"{line}\n\n"
