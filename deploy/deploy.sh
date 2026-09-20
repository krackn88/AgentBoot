#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/dtv-checker}"
REPO_URL="${REPO_URL:-https://github.com/krackn88/AgentBoot.git}"
BRANCH="${BRANCH:-cursor/dtv-checker-88aa}"
PORT="${PORT:-8091}"

echo "==> Deploying DTV Checker to ${APP_DIR}"

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

sudo sed "s/--port 8091/--port ${PORT}/" deploy/dtv-checker.service | sudo tee /etc/systemd/system/dtv-checker.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable dtv-checker
sudo chown -R www-data:www-data "${APP_DIR}/data"
sudo systemctl restart dtv-checker

IP=$(hostname -I | awk '{print $1}')
echo "==> DTV Checker running at http://${IP}:${PORT}"
