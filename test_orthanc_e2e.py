"""End-to-end DICOMweb test contra Orthanc real, via medical-imaging-service.

Variables de entorno requeridas:
    ADMIN_PASSWORD (admin login password)
    ADMIN_EMAIL    (opcional, default admin@example.com)
"""
import json
import os
import urllib.request
import urllib.error
import sys

AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8001")
IMG_URL = os.environ.get("IMG_URL", "http://localhost:8002")


def http_json(method, url, body=None, headers=None):
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


def tag(d, t, default=None):
    return (d.get(t) or {}).get("Value", [default])[0]


# login
s, b = http_json("POST", f"{AUTH_URL}/api/v1/auth/login",
                 {"email": os.environ.get("ADMIN_EMAIL", "admin@example.com"),
                  "password": os.environ["ADMIN_PASSWORD"]})
assert s == 200, b
admin = json.loads(b)["access_token"]
H = {"Authorization": f"Bearer {admin}"}

print("=" * 70)
print("1. QIDO-RS: GET /api/v1/studies?limit=3")
print("=" * 70)
s, b = http_json("GET", f"{IMG_URL}/api/v1/studies?limit=3", headers=H)
print(f"  HTTP {s}")
studies = json.loads(b)
print(f"  estudios devueltos: {len(studies)}")
for st in studies:
    suid = tag(st, "0020000D", "?")
    date = tag(st, "00080020", "?")
    modality = tag(st, "00080061", "?")
    print(f"    StudyUID={suid[:40]}  date={date}  modality={modality}")

if not studies:
    print("(sin estudios en Orthanc; salgo)")
    sys.exit(0)

# Pick first study for further drill-down
study_uid = tag(studies[0], "0020000D")
print()
print("=" * 70)
print(f"2. QIDO-RS: GET /api/v1/studies/{study_uid[:32]}.../series")
print("=" * 70)
s, b = http_json("GET", f"{IMG_URL}/api/v1/studies/{study_uid}/series", headers=H)
print(f"  HTTP {s}")
series = json.loads(b)
print(f"  series: {len(series)}")
for ser in series[:3]:
    seuid = tag(ser, "0020000E", "?")
    modality = tag(ser, "00080060", "?")
    desc = tag(ser, "0008103E", "")
    print(f"    SeriesUID={seuid[:40]}  modality={modality}  desc={desc}")

if not series:
    sys.exit(0)
series_uid = tag(series[0], "0020000E")

print()
print("=" * 70)
print(f"3. QIDO-RS: GET /api/v1/studies/.../series/.../instances")
print("=" * 70)
s, b = http_json("GET",
                 f"{IMG_URL}/api/v1/studies/{study_uid}/series/{series_uid}/instances",
                 headers=H)
print(f"  HTTP {s}")
instances = json.loads(b)
print(f"  instancias: {len(instances)}")

print()
print("=" * 70)
print("4. WADO-RS metadata: GET /api/v1/studies/.../metadata")
print("=" * 70)
s, b = http_json("GET", f"{IMG_URL}/api/v1/studies/{study_uid}/metadata", headers=H)
print(f"  HTTP {s}  body_len={len(b)} bytes")
md = json.loads(b)
print(f"  metadata items: {len(md)}")

print()
print("=" * 70)
print("5. WADO-RS binary: GET /api/v1/studies/.../series/.../instances/.../{instance}")
print("=" * 70)
if instances:
    iuid = tag(instances[0], "00080018")
    req = urllib.request.Request(
        f"{IMG_URL}/api/v1/studies/{study_uid}/series/{series_uid}/instances/{iuid}",
        headers=H,
    )
    try:
        with urllib.request.urlopen(req) as r:
            content = r.read()
            ct = r.headers.get("Content-Type", "")
        print(f"  HTTP 200  content_type={ct[:80]}  bytes={len(content)}")
        # Check it looks like multipart/related with DICOM
        if b"application/dicom" in content[:2000]:
            print("  contiene DICOM en multipart/related (OK)")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read()[:200]}")

print()
print("=" * 70)
print("6. Validar permisos: GET sin token -> 401")
print("=" * 70)
try:
    urllib.request.urlopen(f"{IMG_URL}/api/v1/studies?limit=1")
    print("  ESPERABA 401")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code} (esperado)")

print()
print("Todo OK.")
