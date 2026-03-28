"""API key authentication for AgentRouter."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentrouter.models.db import ApiKey


@dataclass
class AuthContext:
    """Result of successful authentication."""

    api_key_id: str
    provider_api_key: str


def generate_api_key() -> str:
    """Generate a new AgentRouter API key with 'ar-' prefix."""
    return f"ar-{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix(key: str) -> str:
    """Extract displayable prefix from an API key (e.g. 'ar-xxxx...')."""
    return key[:8] + "..."


async def get_api_key_by_hash(
    session: AsyncSession,
    key_hash: str,
) -> ApiKey | None:
    """Look up an API key record by its hash."""
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


class AuthError(Exception):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Invalid or missing API key") -> None:
        self.detail = detail
        super().__init__(detail)


async def authenticate_request(
    *,
    authorization: str | None,
    x_agentrouter_key: str | None,
    session: AsyncSession,
    dev_mode: bool = False,
    dev_openai_api_key: str = "",
) -> AuthContext:
    """
    Authenticate an incoming request and return provider credentials.

    Supports two patterns:
    1. X-AgentRouter-Key header (AR key) + Authorization header (provider key)
    2. Authorization: Bearer ar-... (AR key, provider key stored in DB)

    In dev_mode, authentication is bypassed.
    """
    if dev_mode:
        bearer = _extract_bearer(authorization)
        return AuthContext(
            api_key_id="dev",
            provider_api_key=bearer or dev_openai_api_key,
        )

    bearer = _extract_bearer(authorization)

    if x_agentrouter_key:
        # Pattern 1: AR key in custom header, provider key in Authorization
        agentrouter_key = x_agentrouter_key
        provider_api_key = bearer
    elif bearer and bearer.startswith("ar-"):
        # Pattern 2: AR key in Authorization, provider key stored in DB
        agentrouter_key = bearer
        provider_api_key = None
    else:
        raise AuthError("Missing AgentRouter API key")

    key_hash_value = hash_api_key(agentrouter_key)
    api_key_record = await get_api_key_by_hash(session, key_hash_value)

    if api_key_record is None:
        raise AuthError("Invalid API key")

    if provider_api_key is None:
        # Look up stored provider key
        stored_key = api_key_record.openai_api_key_encrypted
        if not stored_key:
            raise AuthError(
                "No provider API key found. Pass it via Authorization header "
                "or configure it in your AgentRouter dashboard."
            )
        provider_api_key = stored_key

    return AuthContext(
        api_key_id=str(api_key_record.id),
        provider_api_key=provider_api_key,
    )


def _extract_bearer(authorization: str | None) -> str | None:
    """Extract the token from 'Bearer <token>' header value."""
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return authorization.strip()
