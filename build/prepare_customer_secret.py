#!/usr/bin/env python3
"""Inject the license PUBLIC key into the client before the customer build.

The vendor's private signing secret (TROPIC_LICENSE_SECRET / license_secret.txt)
never ships to customers. This script derives the Ed25519 *public* key from it
and writes only that public key into ``tropic_checker/licensing/_secret.py``.
"""

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

    # Import lazily so this runs from the repo root without side effects.
    sys.path.insert(0, str(ROOT))
    os.environ["TROPIC_LICENSE_SECRET"] = secret
    from tropic_checker.licensing.license_core import public_key_hex

    pub_hex = public_key_hex()
    TARGET.write_text(
        '"""Auto-generated at customer build time — do not edit.\n\n'
        "Only the Ed25519 PUBLIC key is embedded here. The private signing key\n"
        'stays on the vendor side and is never shipped to customers.\n"""\n\n'
        f"_LICENSE_PUBLIC_KEY_HEX = {pub_hex!r}\n",
        encoding="utf-8",
    )
    print(f"Wrote public key to {TARGET}")


if __name__ == "__main__":
    main()
