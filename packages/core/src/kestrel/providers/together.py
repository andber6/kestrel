"""Together AI provider adapter — OpenAI-compatible."""

from __future__ import annotations

from typing import Any

import httpx

from kestrel.models.openai import ChatCompletionRequest
from kestrel.providers.openai_compat import OpenAICompatibleProvider

# Fields that Together AI does not support
_UNSUPPORTED_FIELDS = {"logit_bias", "top_logprobs"}


class TogetherProvider(OpenAICompatibleProvider):
    """Together AI API — OpenAI-compatible, strips unsupported fields."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.together.xyz/v1",
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(
            name="together",
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        body = request.model_dump(exclude_none=True)
        for field in _UNSUPPORTED_FIELDS:
            body.pop(field, None)
        # Together doesn't support json_schema response format
        rf = body.get("response_format")
        if isinstance(rf, dict) and rf.get("type") == "json_schema":
            body["response_format"] = {"type": "json_object"}
        return body
