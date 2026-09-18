"""Smoke test helpers for Tropic Time Checker."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import requests

from .api import AccountResult, check_account
from .crypto import aes_encrypt


@dataclass
class SmokeCheck:
    name: str
    status: str  # pass | fail | skip
    detail: str

    @property
    def ok(self) -> bool:
        return self.status != "fail"


def check_crypto() -> SmokeCheck:
    expected = "IIaD9m4+EHijnXVY5bIVjw=="
    actual = aes_encrypt("test")
    if actual == expected:
        return SmokeCheck("crypto", "pass", f"aes_encrypt('test') -> {actual}")
    return SmokeCheck("crypto", "fail", f"expected {expected}, got {actual}")


def check_device_id() -> SmokeCheck:
    from .api import TSCClient

    a = TSCClient().device_id
    b = TSCClient().device_id
    if a != b and len(a) == 36:
        return SmokeCheck("device_id", "pass", f"unique per client ({a[:8]}... vs {b[:8]}...)")
    return SmokeCheck("device_id", "fail", f"device ids not unique: {a}, {b}")


def _proxy_list(proxies: list[str] | None) -> list[str]:
    if proxies:
        return [p.strip() for p in proxies if p.strip()]
    env_proxy = os.environ.get("TROPIC_SMOKE_PROXY", "").strip()
    if env_proxy:
        return [env_proxy]
    return []


def _check_account_with_proxies(
    email: str,
    password: str,
    proxies: list[str] | None,
) -> tuple[AccountResult, str | None]:
    result = check_account(email, password)
    if result.success or not proxies or result.message not in {"Forbidden", "Network error"}:
        return result, None

    for proxy in _proxy_list(proxies):
        proxied = check_account(email, password, proxy=proxy)
        if proxied.success:
            return proxied, proxy
        if proxied.message not in {"Forbidden", "Network error"}:
            return proxied, proxy
    return result, None


def check_api_reachable(proxies: list[str] | None = None) -> SmokeCheck:
    email = f"smoke-{uuid.uuid4().hex[:8]}@invalid.example"
    result, proxy = _check_account_with_proxies(email, "not-a-real-password", proxies)
    if result.message and "Network error" not in result.message:
        via = f" (via proxy)" if proxy else ""
        return SmokeCheck("api_reachable", "pass", f"{result.message}{via}")
    return SmokeCheck(
        "api_reachable",
        "fail",
        result.message or f"status_code={result.status_code}",
    )


def check_api_login(proxies: list[str] | None = None) -> SmokeCheck:
    email = os.environ.get("TROPIC_SMOKE_EMAIL", "").strip()
    password = os.environ.get("TROPIC_SMOKE_PASSWORD", "").strip()
    if not email or not password:
        return SmokeCheck(
            "api_login",
            "skip",
            "set TROPIC_SMOKE_EMAIL and TROPIC_SMOKE_PASSWORD on server",
        )

    result, proxy = _check_account_with_proxies(email, password, proxies)
    if result.success:
        via = " via proxy" if proxy else ""
        return SmokeCheck("api_login", "pass", f"{result.summary_line()}{via}")
    return SmokeCheck("api_login", "fail", result.message or "login failed")


def check_web_health(web_url: str | None) -> SmokeCheck:
    if not web_url:
        return SmokeCheck("web_health", "skip", "no web URL configured")

    url = web_url.rstrip("/") + "/health"
    headers: dict[str, str] = {}
    token = os.environ.get("TROPIC_AUTH_TOKEN", "").strip()
    if token:
        headers["X-Auth-Token"] = token

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        payload = resp.json()
        if resp.ok and payload.get("status") == "ok":
            return SmokeCheck("web_health", "pass", f"{url} -> {payload}")
        return SmokeCheck("web_health", "fail", f"{url} -> HTTP {resp.status_code} {payload}")
    except requests.RequestException as exc:
        return SmokeCheck("web_health", "fail", f"{url} -> {exc}")


def run_smoke_checks(
    *,
    skip_live: bool = False,
    web_url: str | None = None,
    skip_web: bool = False,
    proxies: list[str] | None = None,
) -> tuple[list[SmokeCheck], bool]:
    results: list[SmokeCheck] = [
        check_crypto(),
        check_device_id(),
    ]

    if skip_live:
        results.append(SmokeCheck("api_reachable", "skip", "skipped"))
        results.append(SmokeCheck("api_login", "skip", "skipped"))
    else:
        results.append(check_api_reachable(proxies))
        results.append(check_api_login(proxies))

    if skip_web:
        results.append(SmokeCheck("web_health", "skip", "skipped"))
    else:
        url = web_url or os.environ.get("TROPIC_WEB_URL", "").strip() or None
        results.append(check_web_health(url))

    all_ok = all(r.ok for r in results)
    return results, all_ok
