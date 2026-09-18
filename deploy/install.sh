#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/tropic-checker"
AUTH_TOKEN="${TROPIC_AUTH_TOKEN:-tropic-$(openssl rand -hex 16)}"

echo "Installing Tropic Time Checker to ${APP_DIR}"

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync

mkdir -p "${APP_DIR}"
rsync -a --delete \
  --exclude venv --exclude .git --exclude __pycache__ --exclude data \
  /tmp/tropic-deploy/ "${APP_DIR}/"

python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

mkdir -p "${APP_DIR}/data/data"

SERVICE_FILE="/etc/systemd/system/tropic-checker.service"
OLD_SMOKE_EMAIL=""
OLD_SMOKE_PASSWORD=""
OLD_TELEGRAM_BOT_TOKEN=""
OLD_TELEGRAM_CHAT_ID=""
if [ -f "${SERVICE_FILE}" ]; then
  OLD_SMOKE_EMAIL="$(grep -m1 '^Environment=TROPIC_SMOKE_EMAIL=' "${SERVICE_FILE}" | sed 's/^Environment=TROPIC_SMOKE_EMAIL=//' || true)"
  OLD_SMOKE_PASSWORD="$(grep -m1 '^Environment=TROPIC_SMOKE_PASSWORD=' "${SERVICE_FILE}" | sed 's/^Environment=TROPIC_SMOKE_PASSWORD=//' || true)"
  OLD_TELEGRAM_BOT_TOKEN="$(grep -m1 '^Environment=TELEGRAM_BOT_TOKEN=' "${SERVICE_FILE}" | sed 's/^Environment=TELEGRAM_BOT_TOKEN=//' || true)"
  OLD_TELEGRAM_CHAT_ID="$(grep -m1 '^Environment=TELEGRAM_CHAT_ID=' "${SERVICE_FILE}" | sed 's/^Environment=TELEGRAM_CHAT_ID=//' || true)"
fi

sed "s/CHANGE_ME/${AUTH_TOKEN}/" "${APP_DIR}/deploy/tropic-checker.service" > "${SERVICE_FILE}"

SMOKE_EMAIL="${TROPIC_SMOKE_EMAIL:-${OLD_SMOKE_EMAIL}}"
SMOKE_PASSWORD="${TROPIC_SMOKE_PASSWORD:-${OLD_SMOKE_PASSWORD}}"
if [ -n "${SMOKE_EMAIL}" ] && [ -n "${SMOKE_PASSWORD}" ]; then
  sed -i "/Environment=TROPIC_AUTH_TOKEN/a Environment=TROPIC_SMOKE_EMAIL=${SMOKE_EMAIL}" "${SERVICE_FILE}"
  sed -i "/Environment=TROPIC_SMOKE_EMAIL/a Environment=TROPIC_SMOKE_PASSWORD=${SMOKE_PASSWORD}" "${SERVICE_FILE}"
fi

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${OLD_TELEGRAM_BOT_TOKEN}}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${OLD_TELEGRAM_CHAT_ID}}"
if [ -n "${TELEGRAM_BOT_TOKEN}" ]; then
  sed -i "/Environment=TROPIC_AUTH_TOKEN/a Environment=TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" "${SERVICE_FILE}"
fi
if [ -n "${TELEGRAM_CHAT_ID}" ]; then
  sed -i "/Environment=TELEGRAM_BOT_TOKEN/a Environment=TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}" "${SERVICE_FILE}"
fi

systemctl daemon-reload
systemctl enable tropic-checker
systemctl restart tropic-checker

echo ""
echo "============================================"
echo " Tropic Time Checker is live!"
echo " URL:  http://$(hostname -I | awk '{print $1}'):8080"
echo " Auth: ${AUTH_TOKEN}"
echo "============================================"
