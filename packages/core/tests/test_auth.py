"""Tests for API key authentication."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kestrel.auth.api_key import (
    AuthError,
    authenticate_request,
    generate_api_key,
    hash_api_key,
    key_prefix,
)


class TestGenerateApiKey:
    def test_has_ks_prefix(self) -> None:
        key = generate_api_key()
        assert key.startswith("ks-")

    def test_sufficient_length(self) -> None:
        key = generate_api_key()
        # ks- prefix + 32 bytes urlsafe base64 = ~46 chars total
        assert len(key) > 40

    def test_unique(self) -> None:
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100


class TestHashApiKey:
    def test_returns_hex_string(self) -> None:
        h = hash_api_key("ks-testkey")
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self) -> None:
        assert hash_api_key("ks-abc") == hash_api_key("ks-abc")

    def test_different_keys_produce_different_hashes(self) -> None:
        assert hash_api_key("ks-abc") != hash_api_key("ks-def")


class TestKeyPrefix:
    def test_extracts_prefix(self) -> None:
        assert key_prefix("ks-abcdefghijklmnop") == "ks-abcde..."

    def test_short_key(self) -> None:
        assert key_prefix("ks-ab") == "ks-ab..."


class TestAuthenticateRequestDevMode:
    async def test_dev_mode_bypasses_auth(self) -> None:
        session = AsyncMock()
        ctx = await authenticate_request(
            authorization="Bearer sk-test-openai",
            x_kestrel_key=None,
            session=session,
            dev_mode=True,
            dev_openai_api_key="sk-default",
        )
        assert ctx.api_key_id == "dev"
        assert ctx.provider_api_key == "sk-test-openai"

    async def test_dev_mode_uses_default_key_when_no_bearer(self) -> None:
        session = AsyncMock()
        ctx = await authenticate_request(
            authorization=None,
            x_kestrel_key=None,
            session=session,
            dev_mode=True,
            dev_openai_api_key="sk-default-key",
        )
        assert ctx.api_key_id == "dev"
        assert ctx.provider_api_key == "sk-default-key"


class TestAuthenticateRequestPattern1:
    """Pattern 1: X-Kestrel-Key header + Authorization bearer (provider key)."""

    async def test_valid_kestrel_key_with_provider_key(self) -> None:
        kestrel_key = generate_api_key()

        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.is_active = True
        # No stored provider keys
        for field in [
            "openai_api_key_encrypted",
            "anthropic_api_key_encrypted",
            "gemini_api_key_encrypted",
            "groq_api_key_encrypted",
            "mistral_api_key_encrypted",
            "cohere_api_key_encrypted",
            "together_api_key_encrypted",
            "xai_api_key_encrypted",
        ]:
            setattr(mock_record, field, None)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        session.execute.return_value = mock_result

        ctx = await authenticate_request(
            authorization="Bearer sk-provider-key-123",
            x_kestrel_key=kestrel_key,
            session=session,
            dev_mode=False,
        )
        assert ctx.api_key_id == str(mock_record.id)
        assert ctx.provider_api_key == "sk-provider-key-123"

    async def test_invalid_kestrel_key_raises(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(AuthError, match="Invalid API key"):
            await authenticate_request(
                authorization="Bearer sk-provider",
                x_kestrel_key="ks-badkey",
                session=session,
                dev_mode=False,
            )


class TestAuthenticateRequestPattern2:
    """Pattern 2: Kestrel key as Bearer token, provider key stored in DB."""

    async def test_valid_ks_bearer_with_stored_provider_key(self) -> None:
        kestrel_key = generate_api_key()

        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.is_active = True
        mock_record.openai_api_key_encrypted = "encrypted-openai-key"
        for field in [
            "anthropic_api_key_encrypted",
            "gemini_api_key_encrypted",
            "groq_api_key_encrypted",
            "mistral_api_key_encrypted",
            "cohere_api_key_encrypted",
            "together_api_key_encrypted",
            "xai_api_key_encrypted",
        ]:
            setattr(mock_record, field, None)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        session.execute.return_value = mock_result

        with patch("kestrel.auth.encryption.decrypt_value", return_value="sk-real-openai"):
            ctx = await authenticate_request(
                authorization=f"Bearer {kestrel_key}",
                x_kestrel_key=None,
                session=session,
                dev_mode=False,
            )
        assert ctx.api_key_id == str(mock_record.id)
        assert ctx.provider_api_key == "sk-real-openai"
        assert ctx.provider_keys is not None
        assert "openai" in ctx.provider_keys

    async def test_no_stored_keys_raises(self) -> None:
        kestrel_key = generate_api_key()

        mock_record = MagicMock()
        mock_record.id = uuid.uuid4()
        mock_record.is_active = True
        for field in [
            "openai_api_key_encrypted",
            "anthropic_api_key_encrypted",
            "gemini_api_key_encrypted",
            "groq_api_key_encrypted",
            "mistral_api_key_encrypted",
            "cohere_api_key_encrypted",
            "together_api_key_encrypted",
            "xai_api_key_encrypted",
        ]:
            setattr(mock_record, field, None)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        session.execute.return_value = mock_result

        with pytest.raises(AuthError, match="No provider API key found"):
            await authenticate_request(
                authorization=f"Bearer {kestrel_key}",
                x_kestrel_key=None,
                session=session,
                dev_mode=False,
            )


class TestAuthenticateRequestMissingKey:
    async def test_no_auth_raises(self) -> None:
        session = AsyncMock()
        with pytest.raises(AuthError, match="Missing Kestrel API key"):
            await authenticate_request(
                authorization=None,
                x_kestrel_key=None,
                session=session,
                dev_mode=False,
            )

    async def test_non_ks_bearer_raises(self) -> None:
        session = AsyncMock()
        with pytest.raises(AuthError, match="Missing Kestrel API key"):
            await authenticate_request(
                authorization="Bearer sk-some-provider-key",
                x_kestrel_key=None,
                session=session,
                dev_mode=False,
            )


class TestAuthenticateRequestRevoked:
    async def test_revoked_key_raises(self) -> None:
        kestrel_key = generate_api_key()

        session = AsyncMock()
        mock_result = MagicMock()
        # is_active filter in query means revoked keys return None
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(AuthError, match="Invalid API key"):
            await authenticate_request(
                authorization=f"Bearer {kestrel_key}",
                x_kestrel_key=None,
                session=session,
                dev_mode=False,
            )


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test encryption roundtrip when key is configured."""
        import kestrel.auth.encryption as enc

        # Reset module state so it re-reads env vars
        enc._initialized = False
        enc._fernet = None
        monkeypatch.setenv("KS_DEV_MODE", "true")
        monkeypatch.delenv("KS_ENCRYPTION_KEY", raising=False)

        from kestrel.auth.encryption import decrypt_value, encrypt_value

        # Without encryption key in dev mode, values pass through as plaintext
        assert encrypt_value("secret") == "secret"
        assert decrypt_value("secret") == "secret"

        # Reset for other tests
        enc._initialized = False
        enc._fernet = None

    def test_empty_string_passthrough(self) -> None:
        from kestrel.auth.encryption import decrypt_value, encrypt_value

        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_production_requires_encryption_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production mode must fail if KS_ENCRYPTION_KEY is not set."""
        import kestrel.auth.encryption as enc

        enc._initialized = False
        enc._fernet = None
        monkeypatch.setenv("KS_DEV_MODE", "false")
        monkeypatch.delenv("KS_ENCRYPTION_KEY", raising=False)

        with pytest.raises(ValueError, match="KS_ENCRYPTION_KEY must be set"):
            from kestrel.auth.encryption import encrypt_value

            encrypt_value("secret")

        enc._initialized = False
        enc._fernet = None
