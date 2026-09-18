#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${ROOT}/dist"
RELEASE_DIR="${ROOT}/dist/release"
VERSION="$(date +%Y%m%d)"

cd "${ROOT}"

echo "==> Building Tropic Time Checker (Linux x86_64)"

python3 -m venv "${ROOT}/.build-venv"
"${ROOT}/.build-venv/bin/pip" install --upgrade pip
"${ROOT}/.build-venv/bin/pip" install -r requirements-desktop.txt pyinstaller

export TROPIC_BUILD_ROOT="${ROOT}"
"${ROOT}/.build-venv/bin/pyinstaller" --noconfirm --clean "${ROOT}/build/desktop.spec"

mkdir -p "${RELEASE_DIR}"
ARCHIVE="TropicChecker-linux-x86_64-${VERSION}.tar.gz"
cp "${DIST_DIR}/TropicChecker" "${RELEASE_DIR}/TropicChecker"
chmod +x "${RELEASE_DIR}/TropicChecker"

cat > "${RELEASE_DIR}/README.txt" <<'EOF'
Tropic Time Checker — Linux standalone

Run:
  ./TropicChecker

Data is stored in ~/.tropic-checker/

Optional env vars:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
EOF

tar -czf "${DIST_DIR}/${ARCHIVE}" -C "${RELEASE_DIR}" TropicChecker README.txt
cp "${DIST_DIR}/${ARCHIVE}" "${DIST_DIR}/TropicChecker-linux-x86_64.tar.gz"

echo ""
echo "Built:"
echo "  ${DIST_DIR}/TropicChecker"
echo "  ${DIST_DIR}/${ARCHIVE}"
echo "  ${DIST_DIR}/TropicChecker-linux-x86_64.tar.gz"
ls -lh "${DIST_DIR}/TropicChecker" "${DIST_DIR}/${ARCHIVE}" "${DIST_DIR}/TropicChecker-linux-x86_64.tar.gz"
