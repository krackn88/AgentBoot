#!/usr/bin/env bash
# Run D_PARAMS multi-module search on the dedicated server.
# Usage: BRANCH=cursor/d-params-search-6d23 bash scripts/run_d_search_dedi.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/southwest-checker}"
BRANCH="${BRANCH:-cursor/d-params-search-6d23}"
JOBS="${JOBS:-$(nproc)}"
OUT="${OUT:-/tmp/d_params_multi.json}"
INIT="${INIT:-/tmp/init.json}"

cd "${APP_DIR}"
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull origin "${BRANCH}"

source .venv/bin/activate
pip install -r requirements.txt -q

if [ ! -f "${INIT}" ]; then
  echo "ERROR: ${INIT} missing — copy from cloud agent or fetch init separately"
  exit 1
fi

echo "==> Starting parallel D_PARAMS search with ${JOBS} workers"
PYTHONPATH=. python scripts/search_d_params_multi.py \
  --init "${INIT}" \
  --out "${OUT}" \
  --jobs "${JOBS}" \
  2>&1 | tee /tmp/d_params_multi.log

echo "==> Done. Results: ${OUT}"
