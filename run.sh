#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${ZEUS_PORT:-8093}"
HOST="${ZEUS_HOST:-0.0.0.0}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

export PYTHONPATH="$ROOT"
export ZEUS_DATA_DIR="${ZEUS_DATA_DIR:-$ROOT/data}"

mkdir -p "$ZEUS_DATA_DIR/combos"

echo "Zeus Checker UI → http://localhost:${PORT}"
exec python3 -m uvicorn server.app:app --host "$HOST" --port "$PORT" --reload
