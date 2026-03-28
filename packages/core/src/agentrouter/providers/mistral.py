"""Mistral provider adapter — OpenAI-compatible with minor differences."""

from __future__ import annotations

from typing import Any

import httpx

from agentrouter.models.openai import ChatCompletionRequest
from agentrouter.providers.openai_compat import OpenAICompatibleProvider

# Fields that Mistral does not support
_UNSUPPORTED_FIELDS = {"logprobs", "top_logprobs", "logit_bias"}


class MistralProvider(OpenAICompatibleProvider):
    """Mistral API — mostly OpenAI-compatible, strips unsupported fields."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.mistral.ai/v1",
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(
            name="mistral",
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        body = request.model_dump(exclude_none=True)
        for field in _UNSUPPORTED_FIELDS:
            body.pop(field, None)
        return body
