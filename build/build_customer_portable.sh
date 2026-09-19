#!/usr/bin/env bash
# Portable Windows CUSTOMER package (no install needed) — built from Linux.
#
# Customer edition specifics vs. the standard portable build:
#   * Entry point is run_customer.py (hardware-locked; shows the activation
#     screen on first run and validates against the license server).
#   * Only the vendor Ed25519 PUBLIC key is embedded (derived from your private
#     license_secret.txt). The private signing key never ships to customers.
#   * Bundles Tcl/Tk so the GUI actually launches (the embeddable Python omits it).
#
# NOTE: This produces a working, hardware-locked build but is NOT PyArmor-
# obfuscated (that step requires Windows). For a fully obfuscated single EXE use
# build/build_customer_windows.bat on a Windows machine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/dist/win-portable-customer"
WHEEL_DIR="${ROOT}/dist/win-wheels-customer"
RELEASE_ZIP="${ROOT}/dist/TropicChecker-Customer-windows-x64.zip"
PY_VER="3.12.7"
PY_ZIP="python-${PY_VER}-embed-amd64.zip"
PY_URL="https://www.python.org/ftp/python/${PY_VER}/${PY_ZIP}"

cd "${ROOT}"

# --- Require a signing secret so we can embed the matching PUBLIC key ----------
if [ ! -f "${ROOT}/license_secret.txt" ] && [ -z "${TROPIC_LICENSE_SECRET:-}" ]; then
  echo "ERROR: create license_secret.txt (or set TROPIC_LICENSE_SECRET) first." >&2
  echo "       This is used to embed the vendor PUBLIC key into the client." >&2
  exit 1
fi

rm -rf "${BUILD_DIR}" "${WHEEL_DIR}"
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
"${ROOT}/.winbuild-venv/bin/pip" install --upgrade pip
"${ROOT}/.winbuild-venv/bin/pip" download -r requirements-desktop.txt -d "${WHEEL_DIR}" \
  --platform win_amd64 --python-version 312 --only-binary=:all:

echo "==> Extracting wheels into portable site-packages"
for whl in "${WHEEL_DIR}"/*.whl; do
  unzip -q -o "${whl}" -d "${SITE_PACKAGES}"
done

# --- Inject Tcl/Tk (absent from the embeddable distro) ------------------------
echo "==> Injecting Tcl/Tk (tkinter)"
if ! command -v msiextract >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq msitools
  fi
fi
if ! command -v msiextract >/dev/null 2>&1; then
  echo "ERROR: msiextract is required (sudo apt-get install -y msitools)." >&2
  exit 1
fi
TCLTK_MSI="/tmp/tcltk-${PY_VER}.msi"
TCLTK_OUT="${ROOT}/dist/tcltk-${PY_VER}"
[ -f "${TCLTK_MSI}" ] || curl -fsSL "https://www.python.org/ftp/python/${PY_VER}/amd64/tcltk.msi" -o "${TCLTK_MSI}"
rm -rf "${TCLTK_OUT}"
msiextract -C "${TCLTK_OUT}" "${TCLTK_MSI}" >/dev/null
cp "${TCLTK_OUT}/DLLs/_tkinter.pyd" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/tcl86t.dll" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/tk86t.dll" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/zlib1.dll" "${BUILD_DIR}/"
cp -r "${TCLTK_OUT}/Lib/tkinter" "${SITE_PACKAGES}/tkinter"
cp -r "${TCLTK_OUT}/tcl" "${BUILD_DIR}/tcl"

# --- Embed the vendor PUBLIC key, copy source, then restore repo _secret.py ---
echo "==> Embedding vendor public key into client"
# Deriving the public key needs pycryptodome; install it into the host build venv.
"${ROOT}/.winbuild-venv/bin/pip" install -q pycryptodome
SECRET_FILE="${ROOT}/tropic_checker/licensing/_secret.py"
SECRET_BACKUP="$(mktemp)"
cp "${SECRET_FILE}" "${SECRET_BACKUP}"
trap 'cp "${SECRET_BACKUP}" "${SECRET_FILE}"; rm -f "${SECRET_BACKUP}"' EXIT
"${ROOT}/.winbuild-venv/bin/python" build/prepare_customer_secret.py

echo "==> Copying app source (customer entry point)"
mkdir -p "${BUILD_DIR}/app"
cp -r tropic_checker "${BUILD_DIR}/app/"
cp run_customer.py "${BUILD_DIR}/app/"
# Don't ship the private signing tools or dev secret inside the customer package.
rm -rf "${BUILD_DIR}/app/tropic_checker/__pycache__" 2>/dev/null || true
find "${BUILD_DIR}/app" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Restore the repo's placeholder _secret.py immediately after copying.
cp "${SECRET_BACKUP}" "${SECRET_FILE}"
rm -f "${SECRET_BACKUP}"
trap - EXIT

if [ ! -f "${BUILD_DIR}/_tkinter.pyd" ] || [ ! -f "${SITE_PACKAGES}/tkinter/__init__.py" ] \
   || [ ! -f "${BUILD_DIR}/tcl/tcl8.6/init.tcl" ] \
   || [ ! -f "${BUILD_DIR}/app/run_customer.py" ]; then
  echo "ERROR: customer package incomplete." >&2
  exit 1
fi

cat > "${BUILD_DIR}/TropicChecker.bat" <<'EOF'
@echo off
cd /d "%~dp0"
set "TCL_LIBRARY=%~dp0tcl\tcl8.6"
set "TK_LIBRARY=%~dp0tcl\tk8.6"
start "" pythonw.exe app\run_customer.py
EOF

cat > "${BUILD_DIR}/TropicChecker-console.bat" <<'EOF'
@echo off
cd /d "%~dp0"
set "TCL_LIBRARY=%~dp0tcl\tcl8.6"
set "TK_LIBRARY=%~dp0tcl\tk8.6"
python.exe app\run_customer.py
pause
EOF

cat > "${BUILD_DIR}/README.txt" <<'EOF'
Tropic Time Checker — Licensed Customer Edition (Windows portable)

No Python install required.

First run:
  1. Double-click TropicChecker.bat
  2. Copy your Hardware ID and send it to your vendor
  3. Paste the activation code / license key and click Activate

If the window does not open, run TropicChecker-console.bat to see errors.

This build is locked to one PC per license.
Data folder: %APPDATA%\TropicChecker\
EOF

rm -f "${RELEASE_ZIP}"
(cd "${BUILD_DIR}" && zip -qr "${RELEASE_ZIP}" .)

echo ""
echo "Built: ${RELEASE_ZIP}"
ls -lh "${RELEASE_ZIP}"
