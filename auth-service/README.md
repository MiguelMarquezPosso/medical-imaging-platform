# Auth Service

FastAPI service for user registration, authentication and JWT issuing.
Backed by PostgreSQL (Supabase-compatible).

## Endpoints (mounted under `/api/v1`)
| Method | Path             | Auth          | Description                            |
|--------|------------------|---------------|----------------------------------------|
| POST   | `/auth/register` | none / public | Create a new account (if enabled)      |
| POST   | `/auth/login`    | none          | Email/password → access + refresh JWTs |
| POST   | `/auth/token`    | none          | OAuth2 password flow variant of login  |
| POST   | `/auth/refresh`  | refresh JWT   | Rotate the refresh token, issue new pair |
| POST   | `/auth/logout`   | refresh JWT   | Revoke the refresh token (idempotent)  |
| POST   | `/auth/introspect` | none        | Validate an opaque access token        |
| GET    | `/auth/me`       | access JWT    | Profile of the authenticated user      |
| GET    | `/healthz`       | none          | Liveness                               |
| GET    | `/readyz`        | none          | Readiness (checks DB)                  |

The gateway exposes them at `/auth/...` (the `/api/v1/auth` prefix is stripped).

## Setup

```bash
cp .env.example .env
# Edit DATABASE_URL, JWT_SECRET_KEY (use `openssl rand -hex 64`), domains…

# Make sure the shared network exists
docker network create medimg-internal 2>/dev/null || true

# Run DB + service + migrations
docker compose --env-file .env up -d --build

# Create the initial admin user
docker compose exec auth-service python -m scripts.create_admin admin@example.com 'Sup3rS3cret!Passw0rd'
```

## Architecture
- `app/api/v1/endpoints` — HTTP route handlers (thin)
- `app/services` — application services / use cases
- `app/repositories` — data access (SQLAlchemy async)
- `app/models` — ORM models
- `app/schemas` — Pydantic DTOs
- `app/core` — config, security, errors, logging
- `app/middleware` — request id, logging
- `app/dependencies` — FastAPI dependencies (current user, RBAC)
- `app/db/migrations` — Alembic
- `scripts/` — one-shot helpers

## RBAC
Roles are seeded by the initial migration: `admin`, `radiologist`, `viewer`, `sync-device`.
Each role carries a comma-separated `permissions` string. Use the
`require_roles(...)` and `require_permissions(...)` dependencies to gate routes.

The access JWT carries `roles` and `permissions` claims, so downstream services
(Medical Imaging Service) can authorize locally without round-tripping to Auth.
