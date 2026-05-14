"""HMAC signature verification used by the Raspberry Pi sync flow."""

from __future__ import annotations

import base64
import hmac
from hashlib import sha256

from app.core.config import get_settings


def verify_hmac_signature(body: bytes, signature: str) -> bool:
    """Constant-time HMAC-SHA256 verification.

    The Pi computes `base64(HMAC-SHA256(HMAC_KEY, body))` and sends it in the
    `X-Sync-Signature` header. We recompute and compare.
    """
    s = get_settings()
    if not s.SYNC_HMAC_KEY_BASE64:
        # When no HMAC key is configured, signing is disabled
        return True
    try:
        key = base64.b64decode(s.SYNC_HMAC_KEY_BASE64)
    except Exception:
        return False
    expected = hmac.new(key, body, sha256).digest()
    try:
        provided = base64.b64decode(signature)
    except Exception:
        return False
    return hmac.compare_digest(expected, provided)
