#!/usr/bin/env bash
# Installer for the Raspberry Pi Zero 2 W sync client.
# Run as root on the Pi. Idempotent.

set -euo pipefail

INSTALL_DIR=/opt/medimg-sync
DATA_DIR=/var/lib/medimg-sync
ETC_DIR=/etc/medimg-sync
USER=medimg

echo "==> Ensuring user '${USER}' exists"
id -u "${USER}" >/dev/null 2>&1 || useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin "${USER}"

echo "==> Creating directories"
install -d -m 0750 -o "${USER}" -g "${USER}" "${INSTALL_DIR}"
install -d -m 0750 -o "${USER}" -g "${USER}" "${DATA_DIR}" \
    "${DATA_DIR}/inbox" "${DATA_DIR}/archive" "${DATA_DIR}/quarantine"
install -d -m 0750 -o root -g "${USER}" "${ETC_DIR}"

echo "==> Copying sources"
rsync -a --delete --exclude='.venv' --exclude='__pycache__' \
    ./src/ "${INSTALL_DIR}/src/"
install -m 0644 requirements.txt "${INSTALL_DIR}/requirements.txt"

echo "==> Installing Python dependencies"
sudo -u "${USER}" python3 -m venv "${INSTALL_DIR}/.venv"
sudo -u "${USER}" "${INSTALL_DIR}/.venv/bin/pip" install --no-cache-dir -r "${INSTALL_DIR}/requirements.txt"

if [[ ! -f "${ETC_DIR}/medimg-sync.env" ]]; then
    echo "==> Seeding default env (PLEASE EDIT BEFORE STARTING)"
    install -m 0640 -o root -g "${USER}" .env.example "${ETC_DIR}/medimg-sync.env"
fi

echo "==> Installing systemd unit"
install -m 0644 systemd/medimg-sync.service /etc/systemd/system/medimg-sync.service
systemctl daemon-reload
systemctl enable medimg-sync.service

echo
echo "Edit ${ETC_DIR}/medimg-sync.env, then:"
echo "  systemctl start medimg-sync"
echo "  journalctl -u medimg-sync -f"
