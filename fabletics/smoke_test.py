from __future__ import annotations

import time
from typing import Any

from .checker import _classify_api_error
from .client import FableticsAPIError, FableticsClient
from .config import BASE_URL, TLS_IMPERSONATE
from .proxy import parse_proxy


def _mask_proxy(proxy_url: str | None) -> str:
    if not proxy_url:
        return "none"
    try:
        parsed = parse_proxy(proxy_url) if "://" not in proxy_url else proxy_url
        if "@" in parsed:
            return parsed.split("@", 1)[1]
        return parsed
    except Exception:
        return "configured"


def run_smoke_test(proxy_line: str | None = None) -> dict[str, Any]:
    """Quick end-to-end check: TLS + proxy + guest session + login API."""
    started = time.perf_counter()
    proxy_url: str | None = None
    if proxy_line and proxy_line.strip():
        try:
            proxy_url = parse_proxy(proxy_line.strip())
        except ValueError as exc:
            return {
                "ok": False,
                "tls_profile": TLS_IMPERSONATE,
                "base_url": BASE_URL,
                "proxy": "invalid",
                "error": str(exc),
                "steps": [],
                "total_ms": 0,
            }

    steps: list[dict[str, Any]] = []
    client = FableticsClient(proxy=proxy_url, timeout=25)

    try:
        t0 = time.perf_counter()
        try:
            client.create_guest_session()
            steps.append(
                {
                    "step": "guest_session",
                    "ok": True,
                    "detail": "Guest JWT received",
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
        except Exception as exc:
            steps.append(
                {
                    "step": "guest_session",
                    "ok": False,
                    "detail": str(exc),
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
            return _result(steps, proxy_url, started, ok=False)

        t1 = time.perf_counter()
        probe_email = "smoke-test@fabletics-checker.invalid"
        probe_password = "SmokeTest123!"
        try:
            client.login(probe_email, probe_password)
            steps.append(
                {
                    "step": "login_probe",
                    "ok": True,
                    "status": "HIT",
                    "detail": "Unexpected valid login (API reachable)",
                    "ms": int((time.perf_counter() - t1) * 1000),
                }
            )
        except FableticsAPIError as exc:
            classified = _classify_api_error(exc, probe_email, probe_password)
            status = classified.status
            ok = status in {"FAIL", "BAN"}
            detail = classified.message or str(exc)
            if status == "FAIL":
                detail = "Auth rejected for probe combo (expected — API working)"
            elif status == "BAN":
                detail = "Captcha required on login (API reachable, proxy may be flagged)"
            steps.append(
                {
                    "step": "login_probe",
                    "ok": ok,
                    "status": status,
                    "detail": detail,
                    "ms": int((time.perf_counter() - t1) * 1000),
                }
            )
        except Exception as exc:
            steps.append(
                {
                    "step": "login_probe",
                    "ok": False,
                    "status": "ERROR",
                    "detail": str(exc),
                    "ms": int((time.perf_counter() - t1) * 1000),
                }
            )
    finally:
        client.close()

    ok = all(step.get("ok") for step in steps)
    return _result(steps, proxy_url, started, ok=ok)


def _result(
    steps: list[dict[str, Any]],
    proxy_url: str | None,
    started: float,
    *,
    ok: bool,
) -> dict[str, Any]:
    summary = "All checks passed" if ok else "Smoke test failed"
    if ok and any(s.get("status") == "BAN" for s in steps):
        summary = "API reachable — captcha active on login (try fresh proxy / lower threads)"

    return {
        "ok": ok,
        "summary": summary,
        "tls_profile": TLS_IMPERSONATE,
        "base_url": BASE_URL,
        "proxy": _mask_proxy(proxy_url),
        "steps": steps,
        "total_ms": int((time.perf_counter() - started) * 1000),
    }
