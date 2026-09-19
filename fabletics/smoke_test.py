from __future__ import annotations

import os
import time
from typing import Any

from .checker import _classify_api_error, capture_account_data, parse_combo
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


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email[:2] + "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def _resolve_test_combo(test_combo: str | None = None) -> tuple[str, str] | None:
    line = (test_combo or os.environ.get("FABLETICS_SMOKE_COMBO", "")).strip()
    if not line:
        return None
    return parse_combo(line)


def run_smoke_test(
    proxy_line: str | None = None,
    test_combo: str | None = None,
) -> dict[str, Any]:
    """End-to-end check: TLS + proxy + guest session + login (+ capture if test combo set)."""
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

    test_account = _resolve_test_combo(test_combo)
    steps: list[dict[str, Any]] = []
    client = FableticsClient(proxy=proxy_url, timeout=30)

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
            return _result(steps, proxy_url, started, ok=False, uses_test_account=bool(test_account))

        t1 = time.perf_counter()
        if test_account:
            email, password = test_account
            try:
                login = client.login(email, password)
                data = capture_account_data(client, login.access_token, login.customer)
                credits = int(data.get("member_credits") or 0)
                points = int(data.get("points") or 0)
                steps.append(
                    {
                        "step": "test_account",
                        "ok": True,
                        "status": "HIT",
                        "detail": (
                            f"Login + capture OK for {_mask_email(email)} "
                            f"(credits={credits}, points={points})"
                        ),
                        "ms": int((time.perf_counter() - t1) * 1000),
                    }
                )
            except FableticsAPIError as exc:
                classified = _classify_api_error(exc, email, password)
                steps.append(
                    {
                        "step": "test_account",
                        "ok": False,
                        "status": classified.status,
                        "detail": classified.message or str(exc),
                        "ms": int((time.perf_counter() - t1) * 1000),
                    }
                )
            except Exception as exc:
                steps.append(
                    {
                        "step": "test_account",
                        "ok": False,
                        "status": "ERROR",
                        "detail": str(exc),
                        "ms": int((time.perf_counter() - t1) * 1000),
                    }
                )
        else:
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
    return _result(steps, proxy_url, started, ok=ok, uses_test_account=bool(test_account))


def _result(
    steps: list[dict[str, Any]],
    proxy_url: str | None,
    started: float,
    *,
    ok: bool,
    uses_test_account: bool,
) -> dict[str, Any]:
    if uses_test_account:
        summary = "Test account passed — checker is working" if ok else "Test account check failed"
    elif ok and any(s.get("status") == "BAN" for s in steps):
        summary = "API reachable — captcha active on login (try fresh proxy / lower threads)"
    else:
        summary = "All checks passed" if ok else "Smoke test failed"

    return {
        "ok": ok,
        "summary": summary,
        "mode": "test_account" if uses_test_account else "probe",
        "tls_profile": TLS_IMPERSONATE,
        "base_url": BASE_URL,
        "proxy": _mask_proxy(proxy_url),
        "steps": steps,
        "total_ms": int((time.perf_counter() - started) * 1000),
    }
