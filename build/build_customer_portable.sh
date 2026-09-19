#!/usr/bin/env bash
# Licensed customer Windows portable — built from Linux (no PyArmor).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/dist/customer-portable"
WHEEL_DIR="${ROOT}/dist/win-wheels"
RELEASE_ZIP="${ROOT}/dist/TropicChecker-Customer-windows-x64.zip"
PY_VER="3.12.7"
PY_ZIP="python-${PY_VER}-embed-amd64.zip"
PY_URL="https://www.python.org/ftp/python/${PY_VER}/${PY_ZIP}"

cd "${ROOT}"

if [ ! -f "${ROOT}/license_secret.txt" ] && [ -z "${TROPIC_LICENSE_SECRET:-}" ]; then
  echo "ERROR: Create license_secret.txt or set TROPIC_LICENSE_SECRET (must match license server)"
  exit 1
fi

echo "==> Preparing license signing secret"
python3 build/prepare_customer_secret.py

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${WHEEL_DIR}"

echo "==> Downloading Windows embeddable Python ${PY_VER}"
curl -fsSL "${PY_URL}" -o "/tmp/${PY_ZIP}"
unzip -q -o "/tmp/${PY_ZIP}" -d "${BUILD_DIR}"

SITE_PACKAGES="${BUILD_DIR}/Lib/site-packages"
mkdir -p "${SITE_PACKAGES}"

cat > "${BUILD_DIR}/python312._pth" <<'EOF'
python312.zip
.
Lib/site-packages
import site
EOF

echo "==> Downloading Windows wheels"
python3 -m venv "${ROOT}/.winbuild-venv"
"${ROOT}/.winbuild-venv/bin/pip" install --upgrade pip -q
"${ROOT}/.winbuild-venv/bin/pip" download -r requirements-desktop.txt -d "${WHEEL_DIR}" \
  --platform win_amd64 --python-version 312 --only-binary=:all: -q

echo "==> Extracting wheels"
for whl in "${WHEEL_DIR}"/*.whl; do
  unzip -q -o "${whl}" -d "${SITE_PACKAGES}"
done

echo "==> Copying customer app"
mkdir -p "${BUILD_DIR}/app"
cp -r tropic_checker "${BUILD_DIR}/app/"
cp run_customer.py "${BUILD_DIR}/app/"

cat > "${BUILD_DIR}/TropicChecker.bat" <<'EOF'
@echo off
cd /d "%~dp0"
start "" pythonw.exe app\run_customer.py
EOF

cat > "${BUILD_DIR}/TropicChecker-console.bat" <<'EOF'
@echo off
cd /d "%~dp0"
python.exe app\run_customer.py
pause
EOF

cat > "${BUILD_DIR}/README.txt" <<'EOF'
Tropic Time Checker — Licensed Customer Edition

1. Run TropicChecker.bat
2. Copy your Hardware ID and send it to your vendor
3. Enter the activation code they send you (Online tab)
4. Click Activate Online

If the window does not open, use TropicChecker-console.bat to see errors.

Data folder: %USERPROFILE%\.tropic-checker\
License: %APPDATA%\TropicChecker\license.key

This build is locked to one PC per license.
EOF

rm -f "${RELEASE_ZIP}"
(cd "${BUILD_DIR}" && zip -qr "${RELEASE_ZIP}" .)

echo ""
echo "Built: ${RELEASE_ZIP}"
ls -lh "${RELEASE_ZIP}"
