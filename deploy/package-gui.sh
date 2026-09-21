#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dtv-checker-gui.zip"

cd "${ROOT}"
zip -r "${OUT}" dtv-gui -x "*.pyc" -x "*__pycache__*" -x "dtv-gui/.venv/*"
mkdir -p "${ROOT}/server/static/downloads"
cp "${OUT}" "${ROOT}/server/static/downloads/"
echo "Created ${OUT}"
echo "Web download: /static/downloads/dtv-checker-gui.zip"
