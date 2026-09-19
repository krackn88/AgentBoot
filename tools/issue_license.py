#!/usr/bin/env python3
"""Admin tool — issue hardware-bound license keys for customers.

Usage:
  export TROPIC_LICENSE_SECRET='your-long-random-secret'
  python tools/issue_license.py --hwid ABCD-1234-... --customer "Customer Name"
  python tools/issue_license.py --hwid ABCD-1234 --customer "Trial" --days 30

Never ship this script or the secret in customer builds.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_secret() -> None:
    secret_file = ROOT / "license_secret.txt"
    if secret_file.is_file():
        os.environ.setdefault("TROPIC_LICENSE_SECRET", secret_file.read_text(encoding="utf-8").strip())
    secret = os.environ.get("TROPIC_LICENSE_SECRET", "").strip()
    if not secret or secret.startswith("DEV-ONLY"):
        print(
            "Set TROPIC_LICENSE_SECRET or create license_secret.txt with your signing secret.",
            file=sys.stderr,
        )
        sys.exit(1)
    import tropic_checker.licensing._secret as secret_mod

    secret_mod._LICENSE_SECRET = secret.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a Tropic Checker customer license")
    parser.add_argument("--hwid", required=True, help="Customer hardware id (with or without dashes)")
    parser.add_argument("--customer", required=True, help="Customer label / name")
    parser.add_argument("--days", type=int, default=0, help="Optional expiry in days (0 = never)")
    args = parser.parse_args()

    _load_secret()
    from tropic_checker.licensing.license_core import issue_license

    expires_at = None
    if args.days > 0:
        expires_at = int(time.time()) + args.days * 86400

    key = issue_license(args.hwid, args.customer, expires_at=expires_at)
    print("License issued successfully.\n")
    print(f"Customer: {args.customer}")
    print(f"Hardware: {args.hwid.replace('-', '').upper()}")
    if expires_at:
        print(f"Expires:  {time.strftime('%Y-%m-%d', time.localtime(expires_at))}")
    else:
        print("Expires:  never")
    print("\nLicense key (send to customer):\n")
    print(key)


if __name__ == "__main__":
    main()
