"""Symmetric encryption for provider API keys stored at rest.

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the cryptography library.
The encryption key is loaded from the KS_ENCRYPTION_KEY environment variable.
When no key is configured, values are stored and returned as plaintext
for backwards compatibility during development.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_fernet = None
_initialized = False


def _get_fernet():  # type: ignore[no-untyped-def]
    """Lazily initialize Fernet with the encryption key."""
    global _fernet, _initialized
    if _initialized:
        return _fernet

    _initialized = True
    key = os.environ.get("KS_ENCRYPTION_KEY", "")
    if not key:
        logger.warning(
            "KS_ENCRYPTION_KEY not set — provider keys stored as plaintext"
        )
        return None

    try:
        from cryptography.fernet import Fernet

        _fernet = Fernet(key.encode())
        logger.info("Provider key encryption enabled")
    except Exception:
        logger.exception("Invalid KS_ENCRYPTION_KEY — falling back to plaintext")

    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns ciphertext or plaintext if no key."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Handles both encrypted and legacy plaintext."""
    if not stored:
        return stored
    f = _get_fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except Exception:
        # Value is likely legacy plaintext (not encrypted)
        return stored
