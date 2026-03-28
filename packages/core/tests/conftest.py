"""Shared test fixtures for Kestrel."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from kestrel.app import create_app
from kestrel.config import Settings
from kestrel.services.proxy import ProxyService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://localhost:5432/kestrel_test",
        openai_base_url="https://api.openai.com/v1",
        dev_mode=True,
        dev_openai_api_key="sk-test-key",
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = create_app(settings)

    # Manually set up app state that would normally be set by the lifespan.
    # This avoids needing a real DB connection in tests.
    http_client = httpx.AsyncClient()
    app.state.http_client = http_client
    app.state.db_engine = MagicMock()
    app.state.session_factory = AsyncMock()
    app.state.proxy_service = ProxyService(
        http_client=http_client,
        settings=settings,
        log_service=None,  # No DB logging in tests
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    await http_client.aclose()


SAMPLE_CHAT_REQUEST = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello, world!"}],
}

SAMPLE_OPENAI_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello! How can I help you?"},
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 12,
        "completion_tokens": 7,
        "total_tokens": 19,
    },
    "system_fingerprint": "fp_test",
}
