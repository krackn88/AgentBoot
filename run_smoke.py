#!/usr/bin/env python3
"""Smoke test for Tropic Time Checker.

Usage:
  python run_smoke.py
  python run_smoke.py --skip-live
  python run_smoke.py --web-url http://159.69.76.189:8080

Environment:
  TROPIC_SMOKE_EMAIL / TROPIC_SMOKE_PASSWORD  Live login check
  TROPIC_WEB_URL                              Web health URL
  TROPIC_AUTH_TOKEN                           Auth token for protected /health
"""

from __future__ import annotations

import argparse
import os
import sys

from tropic_checker.smoke import run_smoke_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Tropic Time Checker smoke test")
    parser.add_argument("--skip-live", action="store_true", help="Skip live API checks")
    parser.add_argument(
        "--web-url",
        default=os.environ.get("TROPIC_WEB_URL", "").strip() or None,
        help="Web UI base URL for /health check",
    )
    parser.add_argument("--no-web", action="store_true", help="Skip web health check")
    args = parser.parse_args()

    print("Tropic Time Checker — smoke test\n")
    results, all_ok = run_smoke_checks(
        skip_live=args.skip_live,
        web_url=args.web_url,
        skip_web=args.no_web,
    )

    for check in results:
        label = check.status.upper()
        print(f"  [{label}] {check.name}: {check.detail}")

    print()
    if all_ok:
        print("All smoke checks passed.")
        return 0

    failed = [c.name for c in results if c.status == "fail"]
    print(f"FAILED ({len(failed)}): {', '.join(failed)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
