#!/usr/bin/env bash
# Optional parity smoke: runs a minimal Camoufox NAVIGATE config via CLI.
# Exits 0 with SKIP when Camoufox/Playwright are not installed (CI without browser deps).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/src/OpenBulletCLI"
FIXTURE="$ROOT/fixtures/camoufox-smoke.loli"
WL="$ROOT/fixtures/smoke-wordlist.txt"

if ! command -v python3 >/dev/null; then
  echo "SKIP: python3 missing"
  exit 0
fi

if ! python3 -c "import camoufox" 2>/dev/null; then
  echo "SKIP: camoufox python package not installed"
  exit 0
fi

dotnet build "$ROOT/OpenBullet.Linux.sln" -c Release --no-restore >/dev/null 2>&1 || dotnet build "$ROOT/OpenBullet.Linux.sln" -c Release

cd "$CLI"
LOG="$(mktemp)"
set +e
printf '\n' | dotnet run -c Release --no-build -- \
  -c "$FIXTURE" -w "$WL" --wltype Default -b 1 -v 2>&1 | tee "$LOG"
RC=${PIPESTATUS[1]}
set -e

if grep -q "SUCCESS" "$LOG"; then
  echo "Camoufox parity smoke: SUCCESS"
  exit 0
fi

echo "Camoufox parity smoke failed (exit $RC)"
cat "$LOG"
exit 1
