"""AES-256-GCM encryption used by the Raspberry Pi sync flow.

Wire format (all big-endian, single buffer):

    +----+-----+------------+
    | v1 | iv  | ciphertext |
    |  1 | 12  |     N      |
    +----+-----+------------+
    |                       |
    |  GCM tag is appended  |
    |  by AESGCM (16 bytes) |
    +-----------------------+

The first byte is a version marker so we can rotate the wire format if needed.
"""

from __future__ import annotations

import base64
import os
import secrets
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.errors import ValidationError

VERSION = b"\x01"
IV_LEN = 12


class SyncCrypto(Protocol):
    def encrypt(self, plaintext: bytes, *, aad: bytes | None = None) -> bytes: ...
    def decrypt(self, ciphertext: bytes, *, aad: bytes | None = None) -> bytes: ...


class AesGcmCrypto:
    """AES-256-GCM with a single rotation-friendly key."""

    def __init__(self, key: bytes | None = None) -> None:
        if key is None:
            key = self._load_key_from_env()
        if len(key) != 32:
            raise ValueError("AES key must be 32 bytes (AES-256)")
        self._aead = AESGCM(key)

    @staticmethod
    def _load_key_from_env() -> bytes:
        s = get_settings()
        try:
            key = base64.b64decode(s.SYNC_AES_KEY_BASE64)
        except Exception as exc:
            raise RuntimeError("SYNC_AES_KEY_BASE64 is not valid base64") from exc
        return key

    def encrypt(self, plaintext: bytes, *, aad: bytes | None = None) -> bytes:
        iv = os.urandom(IV_LEN)
        ct = self._aead.encrypt(iv, plaintext, aad)
        return VERSION + iv + ct

    def decrypt(self, ciphertext: bytes, *, aad: bytes | None = None) -> bytes:
        if len(ciphertext) < 1 + IV_LEN + 16:
            raise ValidationError("Encrypted payload too short")
        if not secrets.compare_digest(ciphertext[:1], VERSION):
            raise ValidationError("Unsupported encryption version")
        iv = ciphertext[1 : 1 + IV_LEN]
        ct = ciphertext[1 + IV_LEN :]
        try:
            return self._aead.decrypt(iv, ct, aad)
        except Exception as exc:  # noqa: BLE001 — opaque on purpose
            raise ValidationError("Failed to decrypt payload (bad key or tampered data)") from exc
