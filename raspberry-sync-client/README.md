# Raspberry Pi Sync Client

Edge sync client for a Raspberry Pi Zero 2 W connected to an imaging workstation.

## What it does
- Watches a folder (default `/var/lib/medimg-sync/inbox`) for new `.dcm` files.
- When the internet is reachable, encrypts each file with **AES-256-GCM** (AAD =
  device ID) and uploads it to `POST /sync/upload` on the gateway over HTTPS.
- Authenticates as a user with role `sync-device`. Tokens are refreshed
  automatically. The body is optionally HMAC-signed.
- Persists state in a local SQLite DB so reboots and long offline windows are safe.
- Successful uploads are moved to `archive/`. Rejections (4xx) move to
  `quarantine/`. Network errors are retried with exponential backoff.

## Install on a Pi

```bash
git clone <this repo> /tmp/medimg-sync
cd /tmp/medimg-sync
sudo bash scripts/install.sh
sudoedit /etc/medimg-sync/medimg-sync.env   # fill in real values
sudo systemctl start medimg-sync
journalctl -u medimg-sync -f
```

## Run with docker (for testing on any machine)

```bash
cp .env.example .env
# Edit .env
docker compose up -d --build
# Drop .dcm files into ./data/inbox/
```

## Required env
- `API_BASE_URL` — public gateway URL (HTTPS)
- `SYNC_DEVICE_EMAIL` + `SYNC_DEVICE_PASSWORD` — created via the Auth Service
  and granted the `sync-device` role
- `SYNC_DEVICE_ID` — short stable id (e.g. `pi-ward3-001`) — used as AES AAD
- `SYNC_AES_KEY_BASE64` — must match the imaging service's key
- `SYNC_HMAC_KEY_BASE64` — optional; if set, must match the server

## Wire format
```
[VERSION:1][IV:12][CIPHERTEXT+TAG:N+16]
```
AES-256-GCM with AAD = device ID. The server rejects payloads that decrypt with
a different AAD or that have been tampered with.
