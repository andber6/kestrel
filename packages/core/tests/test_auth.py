"""Tests for API key authentication."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentrouter.auth.api_key import (
    AuthError,
    authenticate_request,
    generate_api_key,
    hash_api_key,
    key_prefix,
)
from agentrouter.models.db import ApiKey


def _make_api_key_record(
    key_hash: str,
    *,
    is_active: bool = True,
    openai_api_key_encrypted: str | None = None,
) -> ApiKey:
    """Create a mock ApiKey record."""
    record = MagicMock(spec=ApiKey)
    record.id = uuid.uuid4()
    record.key_hash = key_hash
    record.is_active = is_active
    record.openai_api_key_encrypted = openai_api_key_encrypted
    return record


def _mock_session(return_record: ApiKey | None = None) -> AsyncMock:
    """Create a mock async session that returns the given record."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_record
    session.execute.return_value = result
    return session


class TestKeyUtilities:
    def test_generate_api_key_has_prefix(self) -> None:
        key = generate_api_key()
        assert key.startswith("ar-")
        assert len(key) > 10

    def test_hash_is_deterministic(self) -> None:
        key = "ar-test-key-123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self) -> None:
        assert hash_api_key("ar-key-1") != hash_api_key("ar-key-2")

    def test_key_prefix_format(self) -> None:
        assert key_prefix("ar-abcdefghijk") == "ar-abcde..."


class TestDevMode:
    async def test_dev_mode_bypasses_auth(self) -> None:
        session = _mock_session()
        ctx = await authenticate_request(
            authorization="Bearer sk-real-openai-key",
            x_agentrouter_key=None,
            session=session,
            dev_mode=True,
        )
        assert ctx.api_key_id == "dev"
        assert ctx.provider_api_key == "sk-real-openai-key"
        session.execute.assert_not_called()

    async def test_dev_mode_uses_fallback_key(self) -> None:
        session = _mock_session()
        ctx = await authenticate_request(
            authorization=None,
            x_agentrouter_key=None,
            session=session,
            dev_mode=True,
            dev_openai_api_key="sk-dev-fallback",
        )
        assert ctx.provider_api_key == "sk-dev-fallback"


class TestPattern1CustomHeader:
    async def test_ar_key_in_custom_header_provider_in_auth(self) -> None:
        ar_key = "ar-test-key"
        hashed = hash_api_key(ar_key)
        record = _make_api_key_record(hashed)
        session = _mock_session(record)

        ctx = await authenticate_request(
            authorization="Bearer sk-openai-key",
            x_agentrouter_key=ar_key,
            session=session,
        )
        assert ctx.api_key_id == str(record.id)
        assert ctx.provider_api_key == "sk-openai-key"


class TestPattern2BearerAR:
    async def test_ar_key_in_bearer_provider_from_db(self) -> None:
        ar_key = "ar-stored-key"
        hashed = hash_api_key(ar_key)
        record = _make_api_key_record(
            hashed, openai_api_key_encrypted="sk-from-db"
        )
        session = _mock_session(record)

        ctx = await authenticate_request(
            authorization=f"Bearer {ar_key}",
            x_agentrouter_key=None,
            session=session,
        )
        assert ctx.provider_api_key == "sk-from-db"

    async def test_ar_key_no_stored_provider_key_raises(self) -> None:
        ar_key = "ar-no-provider"
        hashed = hash_api_key(ar_key)
        record = _make_api_key_record(hashed, openai_api_key_encrypted=None)
        session = _mock_session(record)

        with pytest.raises(AuthError, match="No provider API key found"):
            await authenticate_request(
                authorization=f"Bearer {ar_key}",
                x_agentrouter_key=None,
                session=session,
            )


class TestAuthErrors:
    async def test_missing_all_headers(self) -> None:
        session = _mock_session()
        with pytest.raises(AuthError, match="Missing AgentRouter API key"):
            await authenticate_request(
                authorization=None,
                x_agentrouter_key=None,
                session=session,
            )

    async def test_non_ar_bearer_without_custom_header(self) -> None:
        session = _mock_session()
        with pytest.raises(AuthError, match="Missing AgentRouter API key"):
            await authenticate_request(
                authorization="Bearer sk-just-openai-key",
                x_agentrouter_key=None,
                session=session,
            )

    async def test_invalid_ar_key(self) -> None:
        session = _mock_session(return_record=None)
        with pytest.raises(AuthError, match="Invalid API key"):
            await authenticate_request(
                authorization="Bearer ar-does-not-exist",
                x_agentrouter_key=None,
                session=session,
            )
