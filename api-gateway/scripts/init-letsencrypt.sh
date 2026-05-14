#!/usr/bin/env bash
# Bootstraps a Let's Encrypt certificate for the gateway domain.
# Usage: GATEWAY_DOMAIN=api.example.com TLS_CONTACT_EMAIL=ops@example.com ./scripts/init-letsencrypt.sh

set -euo pipefail

: "${GATEWAY_DOMAIN:?GATEWAY_DOMAIN is required}"
: "${TLS_CONTACT_EMAIL:?TLS_CONTACT_EMAIL is required}"

STAGING="${STAGING:-0}"  # set to 1 for the LE staging environment while testing

COMPOSE="docker compose"

echo "==> Creating shared internal docker network if missing"
docker network inspect medimg-internal >/dev/null 2>&1 || docker network create medimg-internal

echo "==> Generating dhparam.pem (this may take a few minutes)"
if [[ ! -f ./nginx/ssl/dhparam.pem ]]; then
  mkdir -p ./nginx/ssl
  openssl dhparam -out ./nginx/ssl/dhparam.pem 2048
fi

echo "==> Stopping nginx if running (we'll free :80 for the standalone challenge)"
${COMPOSE} stop api-gateway 2>/dev/null || true
${COMPOSE} rm -f api-gateway 2>/dev/null || true

echo "==> Issuing Let's Encrypt certificate via standalone challenge"
# certbot binds :80 itself, no nginx required. Once we have the cert,
# we start nginx with the real files already in place.
STAGING_ARG=""
[[ "$STAGING" == "1" ]] && STAGING_ARG="--staging"

# Use --entrypoint to a single binary; pass args after the service name.
# Docker compose v2 execs the entrypoint directly (no shell parsing), so
# a multi-arg string like "certbot certonly ..." would be interpreted as
# a single executable path and fail.
${COMPOSE} run --rm -p 80:80 --entrypoint certbot certbot \
  certonly --standalone \
  ${STAGING_ARG} \
  --non-interactive \
  --email ${TLS_CONTACT_EMAIL} \
  -d ${GATEWAY_DOMAIN} \
  --rsa-key-size 2048 \
  --agree-tos \
  --force-renewal

echo "==> Starting nginx with the real cert"
${COMPOSE} up -d api-gateway certbot

echo "==> Done"
