"""Wire-format-compatible AES-256-GCM encryption (matches the server)."""

from __future__ import annotations

import base64
import hmac
import os
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = b"\x01"
IV_LEN = 12


class SyncCrypto:
    def __init__(self, aes_key_b64: str, hmac_key_b64: str | None) -> None:
        try:
            key = base64.b64decode(aes_key_b64)
        except Exception as exc:
            raise ValueError("Invalid SYNC_AES_KEY_BASE64") from exc
        if len(key) != 32:
            raise ValueError("AES key must be 32 bytes (AES-256)")
        self._aead = AESGCM(key)
        self._hmac_key = base64.b64decode(hmac_key_b64) if hmac_key_b64 else None

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> bytes:
        iv = os.urandom(IV_LEN)
        ct = self._aead.encrypt(iv, plaintext, aad)
        return VERSION + iv + ct

    def sign(self, body: bytes) -> str | None:
        if not self._hmac_key:
            return None
        return base64.b64encode(hmac.new(self._hmac_key, body, sha256).digest()).decode()
