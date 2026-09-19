#!/usr/bin/env bash
# Upload customer edition builds to the license server download portal.
set -euo pipefail

DEDI="${TROPIC_DEDI:-root@159.69.76.189}"
REMOTE_DIR="/opt/tropic-checker/downloads/customer"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

SSHPASS="${SSHPASS:-}"
SCP=(scp -o StrictHostKeyChecking=no)
SSH=(ssh -o StrictHostKeyChecking=no)
if [ -n "${SSHPASS}" ]; then
  SCP=(sshpass -e scp -o StrictHostKeyChecking=no)
  SSH=(sshpass -e ssh -o StrictHostKeyChecking=no)
fi

echo "Uploading customer builds to ${DEDI}:${REMOTE_DIR}"
"${SCP[@]}" "${DEDI}:${REMOTE_DIR}" --dry-run 2>/dev/null || true
SSHPASS="${SSHPASS}" "${SSH[@]}" "${DEDI}" "mkdir -p ${REMOTE_DIR}"

for file in \
  TropicChecker-Customer-windows-x64.zip \
  TropicChecker-Customer-linux-x86_64.tar.gz \
  TropicChecker-Customer.exe; do
  src=""
  if [ -f "${ROOT}/dist/customer/release/TropicChecker.exe" ] && [ "${file}" = "TropicChecker-Customer.exe" ]; then
    src="${ROOT}/dist/customer/release/TropicChecker.exe"
  elif [ -f "${ROOT}/dist/${file}" ]; then
    src="${ROOT}/dist/${file}"
  elif [ -f "${ROOT}/dist/TropicChecker-Customer-windows-x64.zip" ] && [ "${file}" = "TropicChecker-Customer-windows-x64.zip" ]; then
    src="${ROOT}/dist/TropicChecker-Customer-windows-x64.zip"
  fi
  if [ -n "${src}" ]; then
    echo "  -> ${file}"
    "${SCP[@]}" "${src}" "${DEDI}:${REMOTE_DIR}/${file}"
  fi
done

# Fallback only when no customer Windows build was produced locally
if [ ! -f "${ROOT}/dist/TropicChecker-Customer-windows-x64.zip" ] \
  && ! "${SSH[@]}" "${DEDI}" "test -f ${REMOTE_DIR}/TropicChecker-Customer-windows-x64.zip" 2>/dev/null; then
  if [ -f "${ROOT}/dist/TropicChecker-windows-x64.zip" ]; then
    echo "  -> TropicChecker-Customer-windows-x64.zip (from standard build fallback)"
    "${SCP[@]}" "${ROOT}/dist/TropicChecker-windows-x64.zip" \
      "${DEDI}:${REMOTE_DIR}/TropicChecker-Customer-windows-x64.zip"
  fi
fi

echo ""
echo "Customer portal: http://159.69.76.189:8082/"
echo "Vendor admin:    http://159.69.76.189:8082/admin"
