#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
dotnet test "$ROOT/OpenBullet.Linux.sln" -c Release --filter "FullyQualifiedName~OpenBullet.Parity"
