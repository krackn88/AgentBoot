#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/southwest-checker}"
REPO_URL="${REPO_URL:-https://github.com/krackn88/AgentBoot.git}"
BRANCH="${BRANCH:-cursor/southwest-checker-web-ui-1af1}"
PORT="${PORT:-8093}"

echo "==> Deploying Southwest Checker to ${APP_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  sudo mkdir -p "${APP_DIR}"
  sudo git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${APP_DIR}"
  sudo chown -R "$(whoami):$(whoami)" "${APP_DIR}"
else
  cd "${APP_DIR}"
  git fetch origin "${BRANCH}"
  git checkout "${BRANCH}"
  git pull origin "${BRANCH}"
fi

cd "${APP_DIR}"
sudo mkdir -p data
if [ -f sensor_config.json ]; then
  cp sensor_config.json data/sensor_config.json
  echo "==> Installed sensor_config.json for capture mode"
elif [ -f deploy/default_sensor_config.json ]; then
  cp deploy/default_sensor_config.json data/sensor_config.json
  echo "==> Installed deploy/default_sensor_config.json for capture mode"
fi
if [ -f deploy/probe_replay.template.json ] && [ ! -f data/probe_replay.json ]; then
  cp deploy/probe_replay.template.json data/probe_replay.json
  echo "==> Installed probe_replay template (replace with captured iOS probe pairs)"
fi

sudo chown -R www-data:www-data data || true
sudo chmod 775 data || true

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  npm install --omit=dev
else
  echo "WARNING: npm not found — APIGuard full bootstrap requires Node.js"
fi

sudo sed "s|--port [0-9]\\+|--port ${PORT}|; s|/opt/southwest-checker|${APP_DIR}|g" deploy/southwest-checker.service | sudo tee /etc/systemd/system/southwest-checker.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable southwest-checker
sudo chown -R www-data:www-data "${APP_DIR}/data" || true
sudo systemctl restart southwest-checker

IP=$(hostname -I | awk '{print $1}')
echo "==> Southwest Checker running at http://${IP}:${PORT}"
