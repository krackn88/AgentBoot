#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${ZEUS_PORT:-8093}"
HOST="${ZEUS_HOST:-0.0.0.0}"

export PYTHONPATH="$ROOT"
export ZEUS_DATA_DIR="${ZEUS_DATA_DIR:-$ROOT/data}"

mkdir -p "$ZEUS_DATA_DIR/combos"

PYTHON=python3
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON=python
elif [[ ! -d .venv ]] && python3 -m venv .venv 2>/dev/null && [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON=python
fi

pip install -q -r requirements.txt

echo "Zeus Checker UI → http://localhost:${PORT}"
exec "$PYTHON" -m uvicorn server.app:app --host "$HOST" --port "$PORT" --reload
