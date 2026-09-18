#!/usr/bin/env bash
# Upload desktop builds to the dedi downloads folder.
set -euo pipefail

DEDI="${TROPIC_DEDI:-root@159.69.76.189}"
REMOTE_DIR="/opt/tropic-checker/downloads"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Uploading desktop builds to ${DEDI}:${REMOTE_DIR}"

if [ -f "${ROOT}/dist/TropicChecker-linux-x86_64.tar.gz" ]; then
  LATEST_LINUX="$(ls -1 "${ROOT}/dist"/TropicChecker-linux-x86_64-*.tar.gz 2>/dev/null | tail -1)"
  if [ -n "${LATEST_LINUX}" ]; then
    cp "${LATEST_LINUX}" "${ROOT}/dist/TropicChecker-linux-x86_64.tar.gz"
  fi
fi

SSHPASS="${SSHPASS:-}" 
SCP=(scp -o StrictHostKeyChecking=no)
if [ -n "${SSHPASS}" ]; then
  SCP=(sshpass -e scp -o StrictHostKeyChecking=no)
fi

for file in \
  TropicChecker-linux-x86_64.tar.gz \
  TropicChecker-windows-x64.zip \
  TropicChecker.exe; do
  if [ -f "${ROOT}/dist/${file}" ]; then
    echo "  -> ${file}"
    "${SCP[@]}" "${ROOT}/dist/${file}" "${DEDI}:${REMOTE_DIR}/${file}"
  fi
done

echo "Done. Downloads: http://159.69.76.189:8080/downloads"
