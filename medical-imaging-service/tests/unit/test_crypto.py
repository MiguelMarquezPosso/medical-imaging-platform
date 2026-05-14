"""AES-256-GCM round-trip tests."""

from __future__ import annotations

import base64
import os

# Bootstrap env BEFORE importing app modules
os.environ.setdefault("PUBLIC_BASE_URL", "https://api.example.com")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 64)
os.environ.setdefault("JWT_ISSUER", "https://api.example.com")
os.environ.setdefault("JWT_AUDIENCE", "medical-imaging-platform")
os.environ.setdefault("DICOMWEB_BASE_URL", "https://orthanc.internal/dicom-web")
os.environ.setdefault("SYNC_AES_KEY_BASE64", base64.b64encode(b"\x42" * 32).decode())

import pytest

from app.core.errors import ValidationError
from app.providers.crypto import AesGcmCrypto


def test_round_trip() -> None:
    crypto = AesGcmCrypto()
    plain = b"DICM" + os.urandom(1024)
    ct = crypto.encrypt(plain, aad=b"device-1")
    assert ct != plain
    out = crypto.decrypt(ct, aad=b"device-1")
    assert out == plain


def test_tamper_detection() -> None:
    crypto = AesGcmCrypto()
    ct = bytearray(crypto.encrypt(b"hello world", aad=b"d"))
    ct[-1] ^= 0xFF
    with pytest.raises(ValidationError):
        crypto.decrypt(bytes(ct), aad=b"d")


def test_aad_mismatch() -> None:
    crypto = AesGcmCrypto()
    ct = crypto.encrypt(b"hello world", aad=b"device-A")
    with pytest.raises(ValidationError):
        crypto.decrypt(ct, aad=b"device-B")
