#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/tropic-checker"
SERVICE_FILE="/etc/systemd/system/license-server.service"
ADMIN_TOKEN="${LICENSE_ADMIN_TOKEN:-license-$(openssl rand -hex 16)}"

OLD_TOKEN=""
if [ -f "${SERVICE_FILE}" ]; then
  OLD_TOKEN="$(grep -m1 '^Environment=LICENSE_ADMIN_TOKEN=' "${SERVICE_FILE}" | sed 's/^Environment=LICENSE_ADMIN_TOKEN=//' || true)"
fi
ADMIN_TOKEN="${LICENSE_ADMIN_TOKEN:-${OLD_TOKEN:-$ADMIN_TOKEN}}"

if [ ! -f "${APP_DIR}/license_secret.txt" ] && [ -f "${APP_DIR}/../license_secret.txt" ]; then
  cp "${APP_DIR}/../license_secret.txt" "${APP_DIR}/license_secret.txt"
fi

mkdir -p "${APP_DIR}/data/license-server"
mkdir -p "${APP_DIR}/downloads/customer"

sed "s/CHANGE_ME/${ADMIN_TOKEN}/" "${APP_DIR}/deploy/license-server.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable license-server
systemctl restart license-server

echo ""
echo "============================================"
echo " License server is live!"
echo " Dashboard: http://$(hostname -I | awk '{print $1}'):8082"
echo " Admin token: ${ADMIN_TOKEN}"
echo "============================================"
