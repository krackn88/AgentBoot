#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Tropic Time Checker.
# Safe to run repeatedly and against cached/partial state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# System packages: python venv support + tkinter for the desktop GUI.
if ! dpkg -s python3-venv >/dev/null 2>&1 || ! dpkg -s python3-tk >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv python3-tk
fi

# Project virtualenv.
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
# Test runner (not shipped in the app requirements).
.venv/bin/pip install pytest -q

# Dev-only license signing secret (gitignored). Real customer builds inject
# their own secret at compile time; this is a throwaway for local dev/tests.
if [ ! -f "license_secret.txt" ]; then
  head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > license_secret.txt
  echo "Generated dev license_secret.txt"
fi

echo "Tropic Time Checker environment ready."
