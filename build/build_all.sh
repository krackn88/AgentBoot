#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "${ROOT}/build/build_linux.sh"
bash "${ROOT}/build/build_windows_portable.sh"
echo ""
echo "All desktop builds ready in ${ROOT}/dist/"
