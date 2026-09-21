#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "========================================"
echo "  DTV Checker - Standalone GUI"
echo "========================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed."
  exit 1
fi

echo "Python: $(python3 --version)"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Starting DTV Checker..."
python main.py
