#!/usr/bin/env python3
"""Inject license signing secret before customer obfuscation build."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "tropic_checker" / "licensing" / "_secret.py"


def main() -> None:
    secret_file = ROOT / "license_secret.txt"
    secret = os.environ.get("TROPIC_LICENSE_SECRET", "").strip()
    if not secret and secret_file.is_file():
        secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret or secret.startswith("DEV-ONLY"):
        print("ERROR: Set TROPIC_LICENSE_SECRET or create license_secret.txt", file=sys.stderr)
        sys.exit(1)

    escaped = secret.encode("utf-8").hex()
    TARGET.write_text(
        '"""Auto-generated at customer build time — do not edit."""\n\n'
        f"_LICENSE_SECRET = bytes.fromhex({escaped!r})\n",
        encoding="utf-8",
    )
    print(f"Wrote signing secret to {TARGET}")


if __name__ == "__main__":
    main()
