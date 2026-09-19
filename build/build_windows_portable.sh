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

# The Windows *embeddable* Python omits Tcl/Tk, so tkinter (and therefore
# customtkinter / the whole GUI) is missing. Inject the matching Tcl/Tk from the
# official python.org component MSI so the portable app actually launches.
echo "==> Injecting Tcl/Tk (tkinter) — absent from embeddable Python"
if ! command -v msiextract >/dev/null 2>&1; then
  echo "    msiextract not found; attempting to install msitools..."
  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq msitools
  fi
fi
if ! command -v msiextract >/dev/null 2>&1; then
  echo "ERROR: msiextract is required to bundle Tcl/Tk. Install it with:" >&2
  echo "         sudo apt-get install -y msitools" >&2
  exit 1
fi

TCLTK_MSI="/tmp/tcltk-${PY_VER}.msi"
TCLTK_OUT="${ROOT}/dist/tcltk-${PY_VER}"
curl -fsSL "https://www.python.org/ftp/python/${PY_VER}/amd64/tcltk.msi" -o "${TCLTK_MSI}"
rm -rf "${TCLTK_OUT}"
msiextract -C "${TCLTK_OUT}" "${TCLTK_MSI}" >/dev/null

# Native modules/DLLs sit next to python.exe in the embeddable layout.
cp "${TCLTK_OUT}/DLLs/_tkinter.pyd" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/tcl86t.dll" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/tk86t.dll" "${BUILD_DIR}/"
cp "${TCLTK_OUT}/DLLs/zlib1.dll" "${BUILD_DIR}/"
# Pure-python tkinter package goes on sys.path (site-packages is enabled).
cp -r "${TCLTK_OUT}/Lib/tkinter" "${SITE_PACKAGES}/tkinter"
# Tcl/Tk runtime script libraries (init.tcl etc.).
cp -r "${TCLTK_OUT}/tcl" "${BUILD_DIR}/tcl"

if [ ! -f "${BUILD_DIR}/_tkinter.pyd" ] || [ ! -f "${SITE_PACKAGES}/tkinter/__init__.py" ] \
   || [ ! -f "${BUILD_DIR}/tcl/tcl8.6/init.tcl" ]; then
  echo "ERROR: Tcl/Tk injection incomplete — GUI would fail on Windows." >&2
  exit 1
fi

echo "==> Copying app source"
mkdir -p "${BUILD_DIR}/app"
cp -r tropic_checker "${BUILD_DIR}/app/"
cp run_checker.py "${BUILD_DIR}/app/"

cat > "${BUILD_DIR}/TropicChecker.bat" <<'EOF'
@echo off
cd /d "%~dp0"
set "TCL_LIBRARY=%~dp0tcl\tcl8.6"
set "TK_LIBRARY=%~dp0tcl\tk8.6"
start "" pythonw.exe app\run_checker.py
EOF

cat > "${BUILD_DIR}/TropicChecker-console.bat" <<'EOF'
@echo off
cd /d "%~dp0"
set "TCL_LIBRARY=%~dp0tcl\tcl8.6"
set "TK_LIBRARY=%~dp0tcl\tk8.6"
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
