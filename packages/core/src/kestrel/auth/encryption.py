"""Symmetric encryption for provider API keys stored at rest.

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the cryptography library.
The encryption key is loaded from the KS_ENCRYPTION_KEY environment variable.
When no key is configured, values are stored and returned as plaintext
for backwards compatibility during development.
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[assignment,misc]
    InvalidToken = Exception  # type: ignore[assignment,misc]

_fernet: Fernet | None = None
_initialized = False
_lock = threading.Lock()


def _get_fernet() -> Fernet | None:
    """Lazily initialize Fernet with the encryption key (thread-safe)."""
    global _fernet, _initialized
    if _initialized:
        return _fernet

    with _lock:
        if _initialized:
            return _fernet

        _initialized = True
        key = os.environ.get("KS_ENCRYPTION_KEY", "")
        if not key:
            logger.warning("KS_ENCRYPTION_KEY not set — provider keys stored as plaintext")
            return None

        if Fernet is None:
            logger.error(
                "cryptography package not installed — cannot encrypt provider keys. "
                "Install with: pip install cryptography"
            )
            return None

        try:
            _fernet = Fernet(key.encode())
            logger.info("Provider key encryption enabled")
        except (ValueError, Exception) as exc:
            raise ValueError(
                "Invalid KS_ENCRYPTION_KEY — must be a valid 32-byte "
                "URL-safe base64-encoded Fernet key. Generate one with: "
                "python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())'"
            ) from exc

    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns ciphertext or plaintext if no key."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    encrypted: str = f.encrypt(plaintext.encode()).decode()
    return encrypted


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Handles both encrypted and legacy plaintext."""
    if not stored:
        return stored
    f = _get_fernet()
    if f is None:
        return stored
    try:
        decrypted: str = f.decrypt(stored.encode()).decode()
        return decrypted
    except InvalidToken:
        # Value is likely legacy plaintext (not encrypted)
        logger.debug("Could not decrypt value — treating as legacy plaintext")
        return stored
