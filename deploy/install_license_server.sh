#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/tropic-checker"
SERVICE_FILE="/etc/systemd/system/license-server.service"
ADMIN_TOKEN="${LICENSE_ADMIN_TOKEN:-license-$(openssl rand -hex 16)}"

OLD_TOKEN=""
OLD_IPS=""
if [ -f "${SERVICE_FILE}" ]; then
  OLD_TOKEN="$(grep -m1 '^Environment=LICENSE_ADMIN_TOKEN=' "${SERVICE_FILE}" | sed 's/^Environment=LICENSE_ADMIN_TOKEN=//' || true)"
  OLD_IPS="$(grep -m1 '^Environment=LICENSE_ADMIN_IPS=' "${SERVICE_FILE}" | sed 's/^Environment=LICENSE_ADMIN_IPS=//' || true)"
fi
ADMIN_TOKEN="${LICENSE_ADMIN_TOKEN:-${OLD_TOKEN:-$ADMIN_TOKEN}}"
# Optional: restrict admin dashboard/API to your own IP(s)/CIDRs. Empty=token-only.
ADMIN_IPS="${LICENSE_ADMIN_IPS:-${OLD_IPS}}"
if [ "${ADMIN_IPS}" = "CHANGE_ME_ADMIN_IPS" ]; then
  ADMIN_IPS=""
fi

if [ ! -f "${APP_DIR}/license_secret.txt" ] && [ -f "${APP_DIR}/../license_secret.txt" ]; then
  cp "${APP_DIR}/../license_secret.txt" "${APP_DIR}/license_secret.txt"
fi

mkdir -p "${APP_DIR}/data/license-server"
mkdir -p "${APP_DIR}/downloads/customer"

sed -e "s|^Environment=LICENSE_ADMIN_TOKEN=.*|Environment=LICENSE_ADMIN_TOKEN=${ADMIN_TOKEN}|" \
    -e "s|^Environment=LICENSE_ADMIN_IPS=.*|Environment=LICENSE_ADMIN_IPS=${ADMIN_IPS}|" \
    "${APP_DIR}/deploy/license-server.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable license-server
systemctl restart license-server

echo ""
echo "============================================"
echo " License server is live!"
echo " Dashboard: http://$(hostname -I | awk '{print $1}'):8082"
echo " Admin token: ${ADMIN_TOKEN}"
if [ -n "${ADMIN_IPS}" ]; then
  echo " Admin IP allowlist: ${ADMIN_IPS}"
else
  echo " Admin IP allowlist: (none) — set LICENSE_ADMIN_IPS to lock admin to your IP"
fi
echo "============================================"
