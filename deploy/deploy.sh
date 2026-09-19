#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fabletics-checker}"
REPO_URL="${REPO_URL:-https://github.com/krackn88/AgentBoot.git}"
BRANCH="${BRANCH:-cursor/checker-ui-dedi-b931}"

echo "==> Deploying Fabletics Checker to ${APP_DIR}"

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

if command -v docker >/dev/null 2>&1; then
  docker compose down || true
  docker compose build --no-cache
  docker compose up -d
  echo "==> Running at http://$(hostname -I | awk '{print $1}'):8080"
else
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  sudo cp deploy/fabletics-checker.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable fabletics-checker
  sudo chown -R www-data:www-data "${APP_DIR}/data"
  sudo systemctl restart fabletics-checker
  echo "==> Running via systemd on port 8090"
fi
