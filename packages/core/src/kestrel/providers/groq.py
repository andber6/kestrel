"""Groq provider adapter — OpenAI-compatible with minor restrictions."""

from __future__ import annotations

from typing import Any

import httpx

from kestrel.models.openai import ChatCompletionRequest
from kestrel.providers.openai_compat import OpenAICompatibleProvider

# Fields that Groq does not support
_UNSUPPORTED_FIELDS = {"logprobs", "top_logprobs", "logit_bias"}


class GroqProvider(OpenAICompatibleProvider):
    """Groq API — mostly OpenAI-compatible, strips unsupported fields."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(
            name="groq",
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        body = request.model_dump(exclude_none=True)
        for field in _UNSUPPORTED_FIELDS:
            body.pop(field, None)
        # Groq doesn't support json_schema response format, only json_object
        rf = body.get("response_format")
        if isinstance(rf, dict) and rf.get("type") == "json_schema":
            body["response_format"] = {"type": "json_object"}
        return body
