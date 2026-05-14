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

echo "==> Creating dummy certificate for ${GATEWAY_DOMAIN}"
${COMPOSE} run --rm --entrypoint "\
  mkdir -p /etc/letsencrypt/live/${GATEWAY_DOMAIN} && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /etc/letsencrypt/live/${GATEWAY_DOMAIN}/privkey.pem \
    -out /etc/letsencrypt/live/${GATEWAY_DOMAIN}/fullchain.pem \
    -subj '/CN=localhost' && \
  cp /etc/letsencrypt/live/${GATEWAY_DOMAIN}/fullchain.pem /etc/letsencrypt/live/${GATEWAY_DOMAIN}/chain.pem" certbot

echo "==> Starting nginx"
${COMPOSE} up -d api-gateway

echo "==> Deleting dummy certificate"
${COMPOSE} run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/${GATEWAY_DOMAIN} && \
  rm -Rf /etc/letsencrypt/archive/${GATEWAY_DOMAIN} && \
  rm -Rf /etc/letsencrypt/renewal/${GATEWAY_DOMAIN}.conf" certbot

echo "==> Requesting real Let's Encrypt certificate"
STAGING_ARG=""
[[ "$STAGING" == "1" ]] && STAGING_ARG="--staging"

${COMPOSE} run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    ${STAGING_ARG} \
    --email ${TLS_CONTACT_EMAIL} \
    -d ${GATEWAY_DOMAIN} \
    --rsa-key-size 2048 \
    --agree-tos \
    --force-renewal" certbot

echo "==> Reloading nginx"
${COMPOSE} exec api-gateway nginx -s reload

echo "==> Done"
