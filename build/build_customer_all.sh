#!/usr/bin/env bash
# Build licensed customer editions for Linux and Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "${ROOT}/build/build_customer_linux.sh"
bash "${ROOT}/build/build_customer_portable.sh"
echo ""
echo "Customer builds ready:"
ls -lh "${ROOT}/dist/TropicChecker-Customer-"* 2>/dev/null || true
