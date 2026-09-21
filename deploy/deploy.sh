#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/zeus-checker}"
REPO_URL="${REPO_URL:-https://github.com/krackn88/AgentBoot.git}"
BRANCH="${BRANCH:-cursor/zeus-checker-cfa6}"
PORT="${PORT:-8093}"

echo "==> Deploying Zeus Checker to ${APP_DIR}"

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
sudo chown -R www-data:www-data data
sudo chmod 775 data

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo sed "s/--port [0-9]\\+/--port ${PORT}/" deploy/zeus-checker.service | sudo tee /etc/systemd/system/zeus-checker.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable zeus-checker
sudo chown -R www-data:www-data "${APP_DIR}/data"
sudo systemctl restart zeus-checker

IP=$(hostname -I | awk '{print $1}')
echo "==> Zeus Checker running at http://${IP}:${PORT}"
