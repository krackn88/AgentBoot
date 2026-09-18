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

sed "s/CHANGE_ME/${AUTH_TOKEN}/" "${APP_DIR}/deploy/tropic-checker.service" > /etc/systemd/system/tropic-checker.service
systemctl daemon-reload
systemctl enable tropic-checker
systemctl restart tropic-checker

echo ""
echo "============================================"
echo " Tropic Time Checker is live!"
echo " URL:  http://$(hostname -I | awk '{print $1}'):8080"
echo " Auth: ${AUTH_TOKEN}"
echo "============================================"
