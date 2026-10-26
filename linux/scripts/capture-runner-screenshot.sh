#!/usr/bin/env bash
# In-app RenderTargetBitmap capture (no scrot/xvfb window grab). Verifies brightness.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_MAIN="${1:-/cursor/stores/self/media/openbullet-linux-runner.png}"
OUT_PHASE2="${2:-/cursor/stores/self/media/openbullet-linux-runner-phase2.png}"
OUT_CROP="${3:-/cursor/stores/self/media/openbullet-linux-runner-crop.png}"
OUT_CHAT="${4:-/cursor/stores/self/media/openbullet-linux-runner-chat.png}"
STATS="${5:-/tmp/openbullet-screenshot-stats.txt}"

DLL="$ROOT/linux/src/OpenBullet.Linux/bin/Release/net8.0/OpenBullet.Linux.dll"
if [[ ! -f "$DLL" ]]; then
  dotnet build "$ROOT/linux/OpenBullet.Linux.sln" -c Release
fi

export OPENBULLET_SCREENSHOT=1
export OPENBULLET_SCREENSHOT_PATH="${OUT_MAIN},${OUT_PHASE2}"
export OPENBULLET_SCREENSHOT_CROP_PATH="$OUT_CROP"
export OPENBULLET_SCREENSHOT_CHAT_PATH="$OUT_CHAT"
export OPENBULLET_SCREENSHOT_STATS="$STATS"

# Software renderer + offscreen display; pixels come from Avalonia bitmap, not X11 grab.
xvfb-run -a --server-args="-screen 0 1280x800x24" \
  dotnet "$DLL" 2>&1 | tee /tmp/openbullet-screenshot.log

python3 "$ROOT/linux/scripts/verify-screenshot-brightness.py" "$OUT_MAIN"
python3 "$ROOT/linux/scripts/verify-screenshot-brightness.py" "$OUT_PHASE2"
if [[ -f "$OUT_CROP" ]]; then
  python3 "$ROOT/linux/scripts/verify-screenshot-brightness.py" "$OUT_CROP"
fi
cat "$STATS"
