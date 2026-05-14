"""Round-trip completo case 2 (Pi sync) → STOW → QIDO.

1. Descarga un DICOM real desde Orthanc (via su REST nativo)
2. Le cambia SOPInstanceUID para que sea un instance NUEVO
3. Lo cifra con AES-256-GCM + HMAC
4. POST /api/v1/sync/upload -> imaging service decifra, parsea, almacena,
   reenvía a Orthanc por STOW-RS
5. Verifica status="forwarded"
6. Vuelve a consultarlo por QIDO via el imaging service para cerrar el loop.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import sys
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import pydicom
from pydicom.uid import generate_uid

AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8001")
IMG_URL = os.environ.get("IMG_URL", "http://localhost:8002")
ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8042")
ORTHANC_USER = os.environ["ORTHANC_USER"]
ORTHANC_PASS = os.environ["ORTHANC_PASS"]

PI_EMAIL = os.environ.get("PI_EMAIL", "pi-ward3@example.com")
PI_PASSWORD = os.environ["PI_PASSWORD"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
DEVICE_ID = os.environ.get("DEVICE_ID", "pi-ward3-001")
AES_KEY_B64 = os.environ["SYNC_AES_KEY_BASE64"]
HMAC_KEY_B64 = os.environ["SYNC_HMAC_KEY_BASE64"]

VERSION = b"\x01"


def basic_auth(user: str, pw: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def req(method, url, body=None, headers=None):
    data = body if isinstance(body, (bytes, bytearray)) else (
        json.dumps(body).encode() if body is not None else None
    )
    r = urllib.request.Request(url, data=data, method=method)
    if isinstance(body, dict):
        r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


# 1. Login admin (para QIDO) y Pi (para sync)
print("=" * 70)
print("1. Login")
print("=" * 70)
_, b, _ = req("POST", f"{AUTH_URL}/api/v1/auth/login",
              {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
admin = json.loads(b)["access_token"]
_, b, _ = req("POST", f"{AUTH_URL}/api/v1/auth/login",
              {"email": PI_EMAIL, "password": PI_PASSWORD})
pi = json.loads(b)["access_token"]
print("  admin OK, pi OK")

# 2. Listar instances en Orthanc y bajar la primera como DICOM crudo
print()
print("=" * 70)
print("2. Descargar DICOM real desde Orthanc")
print("=" * 70)
s, b, _ = req("GET", f"{ORTHANC_URL}/instances",
              headers={"Authorization": basic_auth(ORTHANC_USER, ORTHANC_PASS)})
ids = json.loads(b)
print(f"  Orthanc tiene {len(ids)} instances. Tomo el primero: {ids[0]}")
s, dcm_bytes, _ = req("GET", f"{ORTHANC_URL}/instances/{ids[0]}/file",
                      headers={"Authorization": basic_auth(ORTHANC_USER, ORTHANC_PASS)})
print(f"  bajados {len(dcm_bytes)} bytes")

# 3. Parsear con pydicom y cambiar el SOPInstanceUID para forzar instance nuevo
print()
print("=" * 70)
print("3. Generar SOPInstanceUID nuevo (para que NO sea duplicado)")
print("=" * 70)
ds = pydicom.dcmread(io.BytesIO(dcm_bytes))
old_sop = str(ds.SOPInstanceUID)
new_sop = generate_uid()
ds.SOPInstanceUID = new_sop
ds.file_meta.MediaStorageSOPInstanceUID = new_sop
print(f"  old SOP = {old_sop}")
print(f"  new SOP = {new_sop}")
print(f"  Study   = {ds.StudyInstanceUID}")
print(f"  Series  = {ds.SeriesInstanceUID}")
buf = io.BytesIO()
ds.save_as(buf, enforce_file_format=True)
plaintext = buf.getvalue()
print(f"  re-serializado: {len(plaintext)} bytes")

# 4. Cifrar AES-256-GCM (AAD = device id)
print()
print("=" * 70)
print("4. Cifrar AES-256-GCM + firmar HMAC")
print("=" * 70)
aes_key = base64.b64decode(AES_KEY_B64)
hmac_key = base64.b64decode(HMAC_KEY_B64)
aead = AESGCM(aes_key)
iv = os.urandom(12)
ct = aead.encrypt(iv, plaintext, DEVICE_ID.encode())
wire = VERSION + iv + ct
sig = base64.b64encode(hmac.new(hmac_key, wire, hashlib.sha256).digest()).decode()
print(f"  wire = {len(wire)} bytes")

# 5. POST /sync/upload
print()
print("=" * 70)
print("5. POST /api/v1/sync/upload (debería resultar en STOW a Orthanc)")
print("=" * 70)
s, b, _ = req("POST", f"{IMG_URL}/api/v1/sync/upload", body=wire, headers={
    "Authorization": f"Bearer {pi}",
    "Content-Type": "application/octet-stream",
    "X-Sync-Device-Id": DEVICE_ID,
    "X-Sync-Signature": sig,
})
print(f"  HTTP {s}")
result = json.loads(b)
print(f"  status         = {result['status']}")
print(f"  sop_instance   = {result['sop_instance_uid']}")
print(f"  study_instance = {result['study_instance_uid']}")
print(f"  series         = {result['series_instance_uid']}")
print(f"  sha256         = {result['sha256'][:16]}...")

if result["status"] != "forwarded":
    print()
    print("  !! No quedó forwarded. Revisa logs del imaging service.")
    sys.exit(1)

# 6. Verificar QIDO via el imaging service: el instance nuevo debe aparecer
print()
print("=" * 70)
print("6. QIDO via imaging service: el instance nuevo está en Orthanc?")
print("=" * 70)
study = result["study_instance_uid"]
series = result["series_instance_uid"]
s, b, _ = req("GET",
              f"{IMG_URL}/api/v1/studies/{study}/series/{series}/instances",
              headers={"Authorization": f"Bearer {admin}"})
instances = json.loads(b)
print(f"  HTTP {s}  instances en serie: {len(instances)}")
found = False
for ins in instances:
    sop = (ins.get("00080018") or {}).get("Value", [None])[0]
    marker = "  <-- NUESTRO UPLOAD" if sop == new_sop else ""
    print(f"    {sop}{marker}")
    if sop == new_sop:
        found = True

if not found:
    print("  !! El SOP nuevo no aparece. STOW falló silenciosamente?")
    sys.exit(1)

# 7. WADO: bajar el binario del instance que acabamos de subir
print()
print("=" * 70)
print("7. WADO-RS: bajar de vuelta el binario del instance recién subido")
print("=" * 70)
r = urllib.request.Request(
    f"{IMG_URL}/api/v1/studies/{study}/series/{series}/instances/{new_sop}",
    headers={"Authorization": f"Bearer {admin}"},
)
with urllib.request.urlopen(r) as resp:
    content = resp.read()
    ct = resp.headers.get("Content-Type", "")
print(f"  HTTP 200  content_type={ct[:80]}")
print(f"  bytes={len(content)}")
print(f"  multipart contiene 'application/dicom': {b'application/dicom' in content[:2000]}")

print()
print("Round-trip OK: Pi → cifrado → /sync/upload → decifrado → STOW Orthanc → QIDO/WADO.")
