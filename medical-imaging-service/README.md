# Medical Imaging Service

FastAPI service that exposes a unified DICOMweb façade over:
1. **PACS / Orthanc** behind a private tunnel (DICOMweb: QIDO-RS, WADO-RS, STOW-RS).
2. **Raspberry Pi sync uploads** — encrypted `.dicom` files arriving from edge
   devices, decrypted and forwarded into the same DICOMweb storage, so the
   frontend never sees the difference.

## Public surface (mounted under `/api/v1`)

### QIDO-RS — search
- `GET /studies`
- `GET /studies/{study_uid}/series`
- `GET /studies/{study_uid}/series/{series_uid}/instances`

### WADO-RS — retrieve
- `GET /studies/{study_uid}` (streamed multipart)
- `GET /studies/{study_uid}/metadata`
- `GET /studies/{study_uid}/series/{series_uid}` (streamed)
- `GET /studies/{study_uid}/series/{series_uid}/metadata`
- `GET /studies/{study_uid}/series/{series_uid}/instances/{instance_uid}` (streamed)
- `GET /studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata`

### STOW-RS — store
- `POST /studies` (multipart/related; type="application/dicom")
- `POST /studies/{study_uid}`

### Sync (Raspberry Pi)
- `POST /sync/upload` — AES-256-GCM encrypted payload + optional HMAC signature
- `GET  /sync/records` — recent ingest events (admin / radiologist)
- `GET  /sync/dicomweb-config` — current upstream config
- `PATCH /sync/dicomweb-config` — reconfigure the upstream at runtime (admin)

The gateway maps these to `/api/v1/...` and `/sync/...` externally.

## Architecture (per layer, per domain)

```
app/
├── core/               # config, security, middleware, errors, logging, deps
│   ├── config/         # env-driven + runtime-mutable DICOMweb config
│   ├── security/       # JWT validation, HMAC signature verification
│   ├── middleware/
│   ├── errors/
│   ├── logging/
│   └── dependencies/   # FastAPI Depends() wiring (providers + auth + db)
├── domains/
│   ├── studies/
│   │   ├── presentation/   # routes + schemas (HTTP)
│   │   ├── application/    # use cases
│   │   ├── domain/         # entities + repository protocols
│   │   └── infrastructure/ # repository impls
│   ├── series/             (same structure)
│   ├── instances/          (same structure + STOW)
│   └── sync/               (same structure + audit, AES decrypt, central storage)
├── providers/
│   ├── dicomweb/       # DICOMwebProvider protocol + Orthanc implementation
│   ├── storage/        # filesystem (default), pluggable for S3
│   └── crypto/         # AES-256-GCM AEAD
├── routes/             # **global** router — single place that registers every domain
└── shared/             # utils shared across domains
```

Adding a new domain is a 3-step change:
1. Create `app/domains/<name>/{presentation,application,domain,infrastructure}/`.
2. Export the router as `app.domains.<name>.<name>_router`.
3. Add one `include_router(...)` line in `app/routes/api.py`.

No changes elsewhere.

## Setup

```bash
cp .env.example .env
# Required: DATABASE_URL, JWT_SECRET_KEY (must match Auth Service),
# DICOMWEB_BASE_URL, SYNC_AES_KEY_BASE64

# Shared docker network
docker network create medimg-internal 2>/dev/null || true

docker compose --env-file .env up -d --build
```

## Security model
- All HTTP entry points require a valid JWT (validated locally against the same
  signing key as the Auth Service — no per-request round-trip to Auth).
- `studies:read` / `studies:write` permissions gate retrieval and storage.
- Pi uploads require role `sync-device` (or `admin`).
- Pi uploads are AES-256-GCM encrypted with a 12-byte IV and 16-byte tag.
- Pi uploads can optionally be HMAC-signed; the server verifies the signature
  in constant time. The encryption AAD is bound to the device ID so swapping
  devices invalidates the payload.
- The DICOMweb upstream is reached only through a private tunnel
  (`imaging-private` network — not exposed by docker-compose).
- All DICOMweb configuration (URL, auth, TLS verification) is environment-driven
  and mutable at runtime via `PATCH /sync/dicomweb-config` (admin only).
- Every administrative action and every sync upload writes an `audit_log` row.

## Storage
`STORAGE_BACKEND=filesystem` (default) writes to `STORAGE_ROOT` under a
`incoming/<study>/<series>/<sop>.dcm` layout. Swap in an S3 backend by
implementing `StorageProvider` and wiring it in `app/core/dependencies/providers.py`.

## Tests
```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest -q
```
