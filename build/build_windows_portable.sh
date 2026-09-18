#!/usr/bin/env bash
# Portable Windows package (no install needed) — built from Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/dist/win-portable"
WHEEL_DIR="${ROOT}/dist/win-wheels"
RELEASE_ZIP="${ROOT}/dist/TropicChecker-windows-x64.zip"
PY_VER="3.12.7"
PY_ZIP="python-${PY_VER}-embed-amd64.zip"
PY_URL="https://www.python.org/ftp/python/${PY_VER}/${PY_ZIP}"

cd "${ROOT}"
rm -rf "${BUILD_DIR}" "${WHEEL_DIR}"
mkdir -p "${BUILD_DIR}" "${WHEEL_DIR}"

echo "==> Downloading Windows embeddable Python ${PY_VER}"
curl -fsSL "${PY_URL}" -o "/tmp/${PY_ZIP}"
unzip -q -o "/tmp/${PY_ZIP}" -d "${BUILD_DIR}"

SITE_PACKAGES="${BUILD_DIR}/Lib/site-packages"
mkdir -p "${SITE_PACKAGES}"

# Enable site-packages in embeddable distro
cat > "${BUILD_DIR}/python312._pth" <<'EOF'
python312.zip
.
Lib/site-packages
import site
EOF

echo "==> Downloading Windows wheels"
python3 -m venv "${ROOT}/.winbuild-venv"
"${ROOT}/.winbuild-venv/bin/pip" install --upgrade pip
"${ROOT}/.winbuild-venv/bin/pip" download -r requirements-desktop.txt -d "${WHEEL_DIR}" \
  --platform win_amd64 --python-version 312 --only-binary=:all:

echo "==> Extracting wheels into portable site-packages"
for whl in "${WHEEL_DIR}"/*.whl; do
  unzip -q -o "${whl}" -d "${SITE_PACKAGES}"
done

echo "==> Copying app source"
mkdir -p "${BUILD_DIR}/app"
cp -r tropic_checker "${BUILD_DIR}/app/"
cp run_checker.py "${BUILD_DIR}/app/"

cat > "${BUILD_DIR}/TropicChecker.bat" <<'EOF'
@echo off
cd /d "%~dp0"
start "" pythonw.exe app\run_checker.py
EOF

cat > "${BUILD_DIR}/TropicChecker-console.bat" <<'EOF'
@echo off
cd /d "%~dp0"
python.exe app\run_checker.py
pause
EOF

cat > "${BUILD_DIR}/README.txt" <<'EOF'
Tropic Time Checker — Windows portable (standalone)

No Python install required.

Run:
  Double-click TropicChecker.bat

If the window does not open, use TropicChecker-console.bat to see errors.

Data folder: %USERPROFILE%\.tropic-checker\

Optional Telegram (set before launch):
  set TELEGRAM_BOT_TOKEN=your-token
  set TELEGRAM_CHAT_ID=your-chat-id
EOF

rm -f "${RELEASE_ZIP}"
(cd "${BUILD_DIR}" && zip -qr "${RELEASE_ZIP}" .)

echo ""
echo "Built: ${RELEASE_ZIP}"
ls -lh "${RELEASE_ZIP}"
