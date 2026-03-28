"""OpenAI provider adapter."""

from __future__ import annotations

import httpx

from kestrel.providers.openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API — native format, no translation needed."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(
            name="openai",
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )
