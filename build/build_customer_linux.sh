#!/usr/bin/env bash
# Licensed customer Linux standalone binary.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${ROOT}/dist"
RELEASE_DIR="${ROOT}/dist/customer-linux"
ARCHIVE="${DIST_DIR}/TropicChecker-Customer-linux-x86_64.tar.gz"

cd "${ROOT}"

if [ ! -f "${ROOT}/license_secret.txt" ] && [ -z "${TROPIC_LICENSE_SECRET:-}" ]; then
  echo "ERROR: Create license_secret.txt or set TROPIC_LICENSE_SECRET (must match license server)"
  exit 1
fi

echo "==> Preparing license signing secret"
python3 build/prepare_customer_secret.py

echo "==> Building Tropic Time Checker customer edition (Linux x86_64)"
python3 -m venv "${ROOT}/.customer-build-venv"
"${ROOT}/.customer-build-venv/bin/pip" install --upgrade pip -q
"${ROOT}/.customer-build-venv/bin/pip" install -r requirements-desktop.txt pyinstaller -q

export TROPIC_BUILD_ROOT="${ROOT}"
"${ROOT}/.customer-build-venv/bin/pyinstaller" --noconfirm --clean "${ROOT}/build/customer_linux.spec"

rm -rf "${RELEASE_DIR}"
mkdir -p "${RELEASE_DIR}"
cp "${DIST_DIR}/TropicChecker" "${RELEASE_DIR}/TropicChecker"
chmod +x "${RELEASE_DIR}/TropicChecker"

cat > "${RELEASE_DIR}/README.txt" <<'EOF'
Tropic Time Checker — Licensed Customer Edition (Linux)

1. Run: ./TropicChecker
2. Copy your Hardware ID and send it to your vendor
3. Enter the activation code they send you (Online tab)
4. Click Activate Online

Data folder: ~/.tropic-checker/
License file: ~/.tropic-checker/license.key

This build is locked to one PC per license.
EOF

rm -f "${ARCHIVE}"
tar -czf "${ARCHIVE}" -C "${RELEASE_DIR}" TropicChecker README.txt

echo ""
echo "Built: ${ARCHIVE}"
ls -lh "${ARCHIVE}"
