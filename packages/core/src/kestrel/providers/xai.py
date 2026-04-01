"""xAI Grok provider adapter — OpenAI-compatible."""

from __future__ import annotations

from typing import Any

import httpx

from kestrel.models.openai import ChatCompletionRequest
from kestrel.providers.openai_compat import OpenAICompatibleProvider

# Fields that xAI does not support
_UNSUPPORTED_FIELDS = {"logprobs", "top_logprobs", "logit_bias"}


class XaiProvider(OpenAICompatibleProvider):
    """xAI Grok API — OpenAI-compatible, strips unsupported fields."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.x.ai/v1",
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(
            name="xai",
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        body = request.model_dump(exclude_none=True)
        for field in _UNSUPPORTED_FIELDS:
            body.pop(field, None)
        return body
