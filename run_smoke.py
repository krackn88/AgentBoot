#!/usr/bin/env python3
"""Smoke test for Tropic Time Checker.

Verifies crypto, API reachability, optional live login, and optional web health.

Usage:
  python run_smoke.py
  python run_smoke.py --skip-live          # offline checks only
  python run_smoke.py --web-url http://159.69.76.189:8080

Environment:
  TROPIC_SMOKE_EMAIL / TROPIC_SMOKE_PASSWORD  Live login check
  TROPIC_WEB_URL                              Web health URL (default http://127.0.0.1:8080)
  TROPIC_AUTH_TOKEN                           Auth token for protected /health if required
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

import requests

from tropic_checker.api import check_account
from tropic_checker.crypto import aes_encrypt


def _result(name: str, ok: bool, detail: str) -> tuple[str, bool, str]:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")
    return name, ok, detail


def _skip(name: str, detail: str) -> tuple[str, bool, str]:
    print(f"  [SKIP] {name}: {detail}")
    return name, True, detail


def test_crypto() -> tuple[str, bool, str]:
    expected = "IIaD9m4+EHijnXVY5bIVjw=="
    actual = aes_encrypt("test")
    ok = actual == expected
    return _result("crypto", ok, f"aes_encrypt('test') -> {actual}")


def test_device_id_randomized() -> tuple[str, bool, str]:
    from tropic_checker.api import TSCClient

    a = TSCClient().device_id
    b = TSCClient().device_id
    ok = a != b and len(a) == 36
    return _result("device_id", ok, f"unique per client ({a[:8]}... vs {b[:8]}...)")


def test_api_reachable() -> tuple[str, bool, str]:
    email = f"smoke-{uuid.uuid4().hex[:8]}@invalid.example"
    result = check_account(email, "not-a-real-password")
    ok = bool(result.message) and "Network error" not in result.message
    return _result(
        "api_reachable",
        ok,
        result.message or f"status_code={result.status_code}",
    )


def test_api_login() -> tuple[str, bool, str]:
    email = os.environ.get("TROPIC_SMOKE_EMAIL", "").strip()
    password = os.environ.get("TROPIC_SMOKE_PASSWORD", "").strip()
    if not email or not password:
        return _skip("api_login", "set TROPIC_SMOKE_EMAIL and TROPIC_SMOKE_PASSWORD")

    result = check_account(email, password)
    ok = result.success
    detail = result.summary_line() if ok else (result.message or "login failed")
    return _result("api_login", ok, detail)


def test_web_health(web_url: str | None) -> tuple[str, bool, str]:
    if web_url is None:
        return _skip("web_health", "pass --web-url or set TROPIC_WEB_URL")

    url = web_url.rstrip("/") + "/health"
    headers: dict[str, str] = {}
    token = os.environ.get("TROPIC_AUTH_TOKEN", "").strip()
    if token:
        headers["X-Auth-Token"] = token

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        payload = resp.json()
        ok = resp.ok and payload.get("status") == "ok"
        return _result("web_health", ok, f"{url} -> {payload}")
    except requests.RequestException as exc:
        return _result("web_health", False, f"{url} -> {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tropic Time Checker smoke test")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Skip live API login test (still runs API reachability)",
    )
    parser.add_argument(
        "--web-url",
        default=os.environ.get("TROPIC_WEB_URL", "").strip() or None,
        help="Web UI base URL for /health check",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Skip web health check",
    )
    args = parser.parse_args()

    print("Tropic Time Checker — smoke test\n")

    results: list[tuple[str, bool, str]] = []
    results.append(test_crypto())
    results.append(test_device_id_randomized())

    if args.skip_live:
        results.append(_skip("api_reachable", "--skip-live"))
        results.append(_skip("api_login", "--skip-live"))
    else:
        results.append(test_api_reachable())
        results.append(test_api_login())

    if args.no_web:
        results.append(_skip("web_health", "--no-web"))
    else:
        results.append(test_web_health(args.web_url))

    failed = [name for name, ok, _ in results if not ok]
    print()
    if failed:
        print(f"FAILED ({len(failed)}): {', '.join(failed)}")
        return 1

    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
