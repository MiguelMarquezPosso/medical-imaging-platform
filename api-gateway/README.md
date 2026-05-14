# API Gateway

Edge reverse proxy for the Medical Imaging Platform.

## Responsibilities
- Terminate TLS (HTTPS via Let's Encrypt)
- Route external traffic to internal services on the `medimg-internal` docker network
- Apply per-zone rate limiting and connection limits
- Apply CORS, security headers (HSTS, X-Frame-Options, CSP, etc.)
- Emit JSON access logs with request IDs
- Hide internal service identities (no direct PACS/Orthanc/Supabase exposure)

## Routes
| Path prefix | Upstream service             | Notes                                |
|-------------|------------------------------|--------------------------------------|
| `/auth/`    | `auth-service:8000`          | Login, register, refresh, JWT issuing |
| `/api/`     | `medical-imaging-service:8000` | QIDO/WADO/STOW, studies/series/instances |
| `/sync/`    | `medical-imaging-service:8000` | Raspberry Pi encrypted sync uploads |
| `/healthz`  | gateway itself                | Liveness                              |

## Setup

```bash
cp .env.example .env
# Edit .env with the real GATEWAY_DOMAIN and TLS_CONTACT_EMAIL
# Update nginx/conf.d/default.conf with the real domain (replace api.example.com)

# Bootstrap TLS
chmod +x scripts/init-letsencrypt.sh
GATEWAY_DOMAIN=api.example.com TLS_CONTACT_EMAIL=ops@example.com ./scripts/init-letsencrypt.sh

# Bring up the gateway
docker compose --env-file .env up -d
```

The internal docker network `medimg-internal` is shared with the other repos so
the gateway can resolve `auth-service` and `medical-imaging-service` by name.

## Notes
- No internal service is published with `ports:` — only the gateway exposes 80/443
- Logs are JSON-formatted for easy ingestion (ELK, Loki, Datadog…)
- The gateway never validates JWTs itself — that is the Auth/Imaging services' job;
  the gateway only routes and hardens transport
