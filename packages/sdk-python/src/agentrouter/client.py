"""AgentRouter client — configures OpenAI SDK to route through AgentRouter."""

from __future__ import annotations

from typing import Any

import openai

_DEFAULT_BASE_URL = "http://localhost:8080/v1"


class Client(openai.OpenAI):
    """OpenAI-compatible client pre-configured to use AgentRouter.

    Usage::

        import agentrouter

        client = agentrouter.Client(
            api_key="ar-your-agentrouter-key",
            provider_key="sk-your-openai-key",
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello!"}],
        )

    Args:
        api_key: Your AgentRouter API key (starts with ``ar-``), or a provider
            API key for pass-through mode.
        provider_key: Your LLM provider API key (e.g. OpenAI ``sk-...``).
            Required when using an AgentRouter key.
        base_url: AgentRouter proxy URL. Defaults to ``http://localhost:8080/v1``.
        **kwargs: Additional arguments passed to ``openai.OpenAI``.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        provider_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        **kwargs: Any,
    ) -> None:
        headers: dict[str, str] = dict(kwargs.pop("default_headers", {}))
        effective_api_key: str

        if api_key and api_key.startswith("ar-"):
            # Pattern 1: AR key in custom header, provider key in Authorization
            headers["X-AgentRouter-Key"] = api_key
            effective_api_key = provider_key or "not-set"
        else:
            # Pass-through mode: provider key goes directly in Authorization
            effective_api_key = api_key or provider_key or "not-set"

        super().__init__(
            api_key=effective_api_key,
            base_url=base_url,
            default_headers=headers,
            **kwargs,
        )


class AsyncClient(openai.AsyncOpenAI):
    """Async version of the AgentRouter client.

    Same interface as :class:`Client` but for async usage::

        import agentrouter

        client = agentrouter.AsyncClient(
            api_key="ar-your-key",
            provider_key="sk-your-openai-key",
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello!"}],
        )
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        provider_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        **kwargs: Any,
    ) -> None:
        headers: dict[str, str] = dict(kwargs.pop("default_headers", {}))
        effective_api_key: str

        if api_key and api_key.startswith("ar-"):
            headers["X-AgentRouter-Key"] = api_key
            effective_api_key = provider_key or "not-set"
        else:
            effective_api_key = api_key or provider_key or "not-set"

        super().__init__(
            api_key=effective_api_key,
            base_url=base_url,
            default_headers=headers,
            **kwargs,
        )
