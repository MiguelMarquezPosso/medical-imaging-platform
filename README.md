# Medical Imaging Platform

Modular, secure platform to query, retrieve and store DICOM medical images via
a single public HTTPS API. The frontend talks **only** to the gateway — it
never reaches Orthanc / PACS / Supabase / Pi devices directly.

```
┌─────────────┐        HTTPS         ┌────────────────┐
│  Web App    │ ───────────────────▶ │  API Gateway   │  (Nginx + Let's Encrypt)
└─────────────┘                      └───────┬────────┘
                                             │ /auth/*       │ /api/*  │ /sync/*
                                             ▼               ▼          ▼
                                     ┌────────────┐  ┌──────────────────────┐
                                     │   Auth     │  │   Medical Imaging    │
                                     │  Service   │  │       Service        │
                                     │ (FastAPI)  │  │ (FastAPI, DDD)       │
                                     └─────┬──────┘  └──────┬──────┬────────┘
                                           │                │      │
                                     ┌─────▼─────┐    ┌─────▼───┐  │ private tunnel
                                     │ Postgres  │    │Postgres │  │ (WireGuard / Tailscale)
                                     │ (Supabase)│    │ + audit │  ▼
                                     └───────────┘    └─────────┘  ┌────────────┐
                                                                   │  Orthanc   │
                                                                   │ DICOMweb   │
                                                                   │ (hospital  │
                                                                   │  network)  │
                                                                   └────────────┘

                                     ▲   HTTPS  (encrypted .dcm payloads)
                                     │
                              ┌──────┴────────┐
                              │ Raspberry Pi  │
                              │   Zero 2 W    │
                              │ sync client   │
                              └───────────────┘
```

## Repositories (independent and decoupled)

| Repo                              | Purpose                                                | Stack             |
|-----------------------------------|--------------------------------------------------------|-------------------|
| [`api-gateway/`](./api-gateway)   | TLS termination, routing, rate limit, security headers | Nginx + Certbot   |
| [`auth-service/`](./auth-service) | Users, login, JWT, RBAC                                | FastAPI + Postgres|
| [`medical-imaging-service/`](./medical-imaging-service) | DICOMweb façade, sync ingestion         | FastAPI + DDD     |
| [`raspberry-sync-client/`](./raspberry-sync-client) | Edge client (AES-256-GCM encrypted upload)    | Python + systemd  |

Each repo has its own `Dockerfile`, `docker-compose.yml`, `.env.example`, and
README. They can be deployed independently.

## Two image-acquisition flows — same public API

### Case 1 — Hospital PACS via Orthanc + private tunnel
1. Web app → `https://api.example.com/api/v1/studies?...` (QIDO-RS)
2. Gateway → Medical Imaging Service
3. Medical Imaging Service → Orthanc DICOMweb endpoint **over a private tunnel
   only** (WireGuard, Tailscale, SSH tunnel, Cloudflare Tunnel — any of these
   gives Orthanc a private RFC1918 address from the service's POV).

Orthanc is **never** exposed to the public internet.

### Case 2 — Raspberry Pi sync
1. The Pi watches a local folder for `.dcm` files.
2. When online, it AES-256-GCM encrypts the file (AAD = device id) and POSTs
   the ciphertext to `https://api.example.com/sync/upload` over HTTPS with a
   short-lived JWT (role `sync-device`) and an optional HMAC body signature.
3. The Medical Imaging Service:
   - decrypts the payload
   - persists it to central storage (filesystem by default; pluggable S3)
   - writes an audit-log row
   - forwards the instance to Orthanc via STOW-RS so the same QIDO/WADO
     endpoints can serve it later.

The frontend uses the same QIDO/WADO endpoints regardless of which flow
produced the data.

## Deployment

### Prerequisites
- A server with Docker + Docker Compose.
- A DNS record `api.example.com` → server's public IP.
- Outbound network to Let's Encrypt for ACME.
- A private tunnel between the server and Orthanc (configured outside this repo).

### 1. Create the shared internal network
```bash
docker network create medimg-internal
```

### 2. Generate secrets
```bash
# JWT signing key (use the *same* value for auth-service and medical-imaging-service)
openssl rand -hex 64

# AES-256 key for Pi sync (same value on the imaging service AND each Pi)
openssl rand -base64 32

# Optional HMAC key for body signing
openssl rand -base64 48

# 2048-bit DH params for nginx
mkdir -p api-gateway/nginx/ssl
openssl dhparam -out api-gateway/nginx/ssl/dhparam.pem 2048
```

### 3. Configure each repo
```bash
cd auth-service              && cp .env.example .env  # edit values
cd ../medical-imaging-service && cp .env.example .env  # same JWT_SECRET_KEY!
cd ../api-gateway            && cp .env.example .env
```

Update [`api-gateway/nginx/conf.d/default.conf`](./api-gateway/nginx/conf.d/default.conf):
replace every `api.example.com` with your real domain.

### 4. Bring up the platform

```bash
# 4a. Auth service + DB + migrations
cd auth-service
docker compose --env-file .env up -d --build
docker compose run --rm migrate     # idempotent

# 4b. Medical Imaging Service + DB + migrations
cd ../medical-imaging-service
docker compose --env-file .env up -d --build
docker compose run --rm migrate     # idempotent

# 4c. Gateway (with TLS bootstrap)
cd ../api-gateway
GATEWAY_DOMAIN=api.example.com TLS_CONTACT_EMAIL=ops@example.com \
  bash scripts/init-letsencrypt.sh
docker compose --env-file .env up -d
```

### 5. Create the initial admin user
```bash
cd auth-service
docker compose exec auth-service python -m scripts.create_admin \
    admin@example.com 'Sup3rS3cret!Passw0rd'
```

### 6. Provision a sync device
- Register a user via `POST /auth/register` (or have the admin do it).
- Assign the `sync-device` role:

```sql
-- inside auth-service db
INSERT INTO user_roles(user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
 WHERE u.email='pi-ward3@example.com' AND r.name='sync-device';
```

- Copy `raspberry-sync-client/.env.example` to the Pi, fill in the credentials
  and the shared AES key, and run `scripts/install.sh` on the Pi.

## Configuration is environment-driven
No secret, URL, credential, JWT signing key, DICOMweb endpoint, AES key or DB
connection string is hard-coded anywhere. Every value is read from `.env` /
environment variables. The DICOMweb base URL and credentials are additionally
mutable at runtime via:

```
PATCH /api/v1/sync/dicomweb-config       # admin only
```

…so you can rotate the Orthanc connection without a redeploy.

## Security summary
- **TLS everywhere** at the edge — Mozilla Intermediate ciphers, HSTS, OCSP.
- **JWT** access tokens (short-lived) + rotating refresh tokens stored with
  device fingerprint; revocable from `POST /auth/logout`.
- **RBAC** — `admin`, `radiologist`, `viewer`, `sync-device` (seeded).
- **AES-256-GCM** for Pi → server payloads, with AAD = device id.
- **HMAC-SHA256** body signatures, constant-time verified.
- **Rate limiting** per zone at the gateway (`auth`, `api`, `sync`).
- **Audit log** — every admin action and every sync upload writes a row with
  request id, actor, IP, UA, and a structured payload.
- **No direct PACS exposure** — Orthanc lives on a private docker network and
  is reached only via a private tunnel.
- **Defence in depth** — gateway strips `X-Internal-*` headers, CSP locks down
  the API surface, no service exposes ports other than 80/443 on the gateway.

## Adding a new domain to the Medical Imaging Service
1. Create `app/domains/<name>/{presentation,application,domain,infrastructure}/`.
2. Implement entities + repository protocol in `domain/`, repository impl in
   `infrastructure/`, use cases in `application/`, FastAPI routes in
   `presentation/`.
3. Export the router as `app.domains.<name>.<name>_router`.
4. Add ONE `include_router(...)` line in `app/routes/api.py`. Done.
