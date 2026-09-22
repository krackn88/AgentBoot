#!/usr/bin/env python3
"""Brute-test native probe modes against Southwest login."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from southwest_checker.checker import SouthwestChecker  # noqa: E402


def list_native_modes() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "southwest_checker.apiguard.probe_native"],
        input=json.dumps({"tokens": ["a", "b", "c", "ios"], "mode": "list"}),
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        return []
    return ["hmac-chain", "hmac-token", "hmac-all", "sha256-token"] + [
        f"native-{name}" for name in json.loads(proc.stdout)
    ]


def run_mode(mode: str, username: str, password: str, proxy: str | None) -> str:
    env = dict(os.environ)
    env["SW_PROBE_MODE"] = mode
    checker = SouthwestChecker(full_bootstrap=True, proxy=proxy)
    result = checker.check(username, password, retries=0)
    return result.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-p", "--password", required=True)
    parser.add_argument("--proxy", default=os.environ.get("SW_PROXY"))
    parser.add_argument("--modes", nargs="*", help="Subset of probe modes to test")
    parser.add_argument("--trials", type=int, default=1, help="Login attempts per mode")
    args = parser.parse_args()

    modes = args.modes or list_native_modes()
    summary: dict[str, dict[str, int]] = {}

    for mode in modes:
        counts = {"hit": 0, "retry": 0, "bad": 0, "error": 0}
        for _ in range(args.trials):
            status = run_mode(mode, args.username, args.password, args.proxy)
            counts[status if status in counts else "error"] += 1
        summary[mode] = counts
        print(
            f"{mode:24} hit={counts['hit']} retry={counts['retry']} "
            f"bad={counts['bad']} error={counts['error']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
