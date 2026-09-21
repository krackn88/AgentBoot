#!/usr/bin/env python3
"""CLI entry point for the DirectTV account checker."""

from __future__ import annotations

import argparse
import json
import sys

from dtv.checker import DTVChecker, parse_combo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DirectTV account checker")
    parser.add_argument("combo", nargs="?", help="email:password combo to check")
    parser.add_argument("-f", "--file", help="Path to combo file (email:password per line)")
    parser.add_argument("-j", "--json", action="store_true", help="Print JSON output")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    combos: list[tuple[str, str]] = []
    if args.combo:
        parsed = parse_combo(args.combo)
        if not parsed:
            parser.error("Combo must be in email:password format")
        combos.append(parsed)

    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            for line in handle:
                parsed = parse_combo(line)
                if parsed:
                    combos.append(parsed)

    if not combos:
        parser.error("Provide a combo or --file")

    checker = DTVChecker(timeout=args.timeout)
    exit_code = 0

    for email, password in combos:
        result = checker.check(email, password)
        if args.json:
            print(
                json.dumps(
                    {
                        "email": result.email,
                        "status": result.status,
                        "active": result.active,
                        "account_status": result.account_status,
                        "account_type": result.account_type,
                        "package": result.package,
                        "first_name": result.first_name,
                        "channels": result.channels,
                        "svod_addons": result.svod_addons,
                        "sports_packages": result.sports_packages,
                        "addons": result.addons,
                        "error": result.error,
                    },
                    indent=2,
                )
            )
        else:
            print(result.format_line())
        if result.status == "ERROR":
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
