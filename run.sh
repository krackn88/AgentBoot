#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data
pip install -q -r requirements.txt
exec uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload
