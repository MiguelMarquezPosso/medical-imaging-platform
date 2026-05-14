"""End-to-end test del flujo de upload sincronizado del Raspberry Pi.

Cifra un .dcm de prueba con AES-256-GCM, lo firma con HMAC-SHA256 y lo
sube al medical-imaging-service. Imprime la respuesta paso a paso.

Variables de entorno requeridas (deben coincidir con el .env del
medical-imaging-service):

    SYNC_AES_KEY_BASE64
    SYNC_HMAC_KEY_BASE64
    PI_EMAIL              (opcional, default pi-ward3@example.com)
    PI_PASSWORD
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8001")
IMG_URL = os.environ.get("IMG_URL", "http://localhost:8002")
PI_EMAIL = os.environ.get("PI_EMAIL", "pi-ward3@example.com")
PI_PASSWORD = os.environ["PI_PASSWORD"]
DEVICE_ID = os.environ.get("DEVICE_ID", "pi-ward3-001")
AES_KEY_B64 = os.environ["SYNC_AES_KEY_BASE64"]
HMAC_KEY_B64 = os.environ["SYNC_HMAC_KEY_BASE64"]

VERSION = b"\x01"
IV_LEN = 12


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_bytes(method: str, url: str, body: bytes, headers: dict) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    print("=== 1. Login como Pi ===")
    status, resp = http_json("POST", f"{AUTH_URL}/api/v1/auth/login",
                             {"email": PI_EMAIL, "password": PI_PASSWORD})
    print(f"  HTTP {status}")
    if status != 200:
        print(f"  ERROR: {resp.decode()}")
        return 1
    tokens = json.loads(resp)
    access = tokens["access_token"]
    print(f"  access_token ok ({len(access)} bytes)")

    payload = b"DICM_FAKE_PAYLOAD_FOR_TESTING_ONLY_" + os.urandom(64)
    print(f"\n=== 2. Cifrar payload ({len(payload)} bytes plaintext) ===")
    aes_key = base64.b64decode(AES_KEY_B64)
    aead = AESGCM(aes_key)
    iv = os.urandom(IV_LEN)
    aad = DEVICE_ID.encode()
    ct = aead.encrypt(iv, payload, aad)
    wire = VERSION + iv + ct
    print(f"  ciphertext (wire) = {len(wire)} bytes, AAD = device id '{DEVICE_ID}'")

    print(f"\n=== 3. Firmar HMAC-SHA256 ===")
    hmac_key = base64.b64decode(HMAC_KEY_B64)
    sig = base64.b64encode(hmac.new(hmac_key, wire, hashlib.sha256).digest()).decode()
    print(f"  X-Sync-Signature = {sig[:32]}...")

    print(f"\n=== 4. POST /api/v1/sync/upload ===")
    status, resp = http_bytes("POST", f"{IMG_URL}/api/v1/sync/upload", wire, {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/octet-stream",
        "X-Sync-Device-Id": DEVICE_ID,
        "X-Sync-Signature": sig,
    })
    print(f"  HTTP {status}")
    print(f"  body: {resp.decode()}")

    print(f"\n=== 5. Verificar /api/v1/sync/records (como admin) ===")
    status, resp = http_json("POST", f"{AUTH_URL}/api/v1/auth/login",
                             {"email": os.environ.get("ADMIN_EMAIL", "admin@example.com"),
                              "password": os.environ["ADMIN_PASSWORD"]})
    admin_access = json.loads(resp)["access_token"]
    status, resp = http_json("GET", f"{IMG_URL}/api/v1/sync/records",
                             headers={"Authorization": f"Bearer {admin_access}"})
    print(f"  HTTP {status}")
    print(f"  records: {resp.decode()[:500]}")

    print(f"\n=== 6. Probar HMAC malo (debe 401) ===")
    status, resp = http_bytes("POST", f"{IMG_URL}/api/v1/sync/upload", wire, {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/octet-stream",
        "X-Sync-Device-Id": DEVICE_ID,
        "X-Sync-Signature": "AAAA" + sig[4:],
    })
    print(f"  HTTP {status}: {resp.decode()[:200]}")

    print(f"\n=== 7. Probar device-id distinto (AAD inválida -> 400) ===")
    sig_bad_aad = base64.b64encode(hmac.new(hmac_key, wire, hashlib.sha256).digest()).decode()
    status, resp = http_bytes("POST", f"{IMG_URL}/api/v1/sync/upload", wire, {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/octet-stream",
        "X-Sync-Device-Id": "pi-other-device",
        "X-Sync-Signature": sig_bad_aad,
    })
    print(f"  HTTP {status}: {resp.decode()[:200]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
