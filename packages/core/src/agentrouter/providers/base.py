"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx

from agentrouter.models.openai import ChatCompletionRequest, ChatCompletionResponse


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    api_key: str
    base_url: str
    timeout_connect: float = 5.0
    timeout_read: float = 120.0


class LLMProvider(ABC):
    """Abstract base for all LLM provider adapters."""

    def __init__(self, config: ProviderConfig, http_client: httpx.AsyncClient) -> None:
        self.config = config
        self.http_client = http_client

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'openai', 'anthropic'."""
        ...

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send a non-streaming chat completion request."""
        ...

    @abstractmethod
    def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """
        Send a streaming chat completion request.
        Yields raw SSE lines (e.g. 'data: {...}\\n\\n').
        """
        ...

    @abstractmethod
    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """Translate from OpenAI format to this provider's native format."""
        ...

    @abstractmethod
    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        """Translate from this provider's native response to OpenAI format."""
        ...
