from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .proxy import parse_proxy
from .config import (
    BASE_URL,
    RECAPTCHA_ACTION,
    RECAPTCHA_SITE_KEY,
    TURNSTILE_ACTION,
    TURNSTILE_PAGE_URL,
    TURNSTILE_SITE_KEY,
)

_BALANCE_CACHE_TTL = 30.0
_balance_cache: dict[str, Any] | None = None
_balance_cache_at = 0.0
_local_solver: Callable[[int], str] | None = None
_CLOUD_BALANCE_URL = "https://api.capsolver.com/getBalance"


def register_local_solver(fn: Callable[[int], str] | None) -> None:
    """Use an in-process Camoufox/local solver instead of CapSolver."""
    global _local_solver
    _local_solver = fn


def _solver_base_url() -> str:
    return os.environ.get("CAPSOLVER_API_URL", "https://api.capsolver.com").rstrip("/")


def _uses_local_solver() -> bool:
    if _local_solver is not None:
        return True
    return "api.capsolver.com" not in _solver_base_url().lower()


def _create_task_url() -> str:
    return f"{_solver_base_url()}/createTask"


def _result_task_url() -> str:
    return f"{_solver_base_url()}/getTaskResult"


def _balance_url() -> str:
    if _uses_local_solver():
        return _CLOUD_BALANCE_URL
    return f"{_solver_base_url()}/getBalance"


def captcha_api_key() -> str | None:
    if _local_solver is not None:
        key = os.environ.get("CAPSOLVER_API_KEY", "local-camoufox").strip()
        return key or "local-camoufox"
    key = os.environ.get("CAPSOLVER_API_KEY", "").strip()
    return key or None


def _balance_api_key() -> str | None:
    return (
        os.environ.get("CAPSOLVER_BALANCE_KEY", "").strip()
        or os.environ.get("CAPSOLVER_CLOUD_KEY", "").strip()
        or captcha_api_key()
    )


def needs_captcha(message: str) -> bool:
    lower = message.lower()
    return "recaptcha" in lower or (
        "captcha" in lower and "authentication" not in lower
    )


def turnstile_site_key() -> str | None:
    key = os.environ.get("TURNSTILE_SITE_KEY", TURNSTILE_SITE_KEY).strip()
    return key or None


def _capsolver_post(url: str, payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CapSolver HTTP {exc.code}: {body[:200]}") from exc


def _poll_capsolver_task(api_key: str, task_id: str, timeout: int = 120) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _capsolver_post(
            _result_task_url(),
            {"clientKey": api_key, "taskId": task_id},
            timeout=30,
        )
        status = result.get("status")
        if status == "ready":
            solution = result.get("solution") or {}
            token = solution.get("token") or solution.get("gRecaptchaResponse")
            if token:
                return token
            raise RuntimeError("CapSolver returned no captcha token")
        if status == "failed" or result.get("errorId"):
            raise RuntimeError(result.get("errorDescription") or "CapSolver task failed")
        time.sleep(2)
    raise RuntimeError("CapSolver timed out")


def _create_task(api_key: str, task: dict) -> str:
    result = _capsolver_post(
        _create_task_url(),
        {"clientKey": api_key, "task": task},
    )
    if result.get("errorId"):
        raise RuntimeError(result.get("errorDescription") or "CapSolver createTask failed")
    task_id = result.get("taskId")
    if not task_id:
        raise RuntimeError("CapSolver did not return taskId")
    return task_id


def _solver_proxy(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    raw = (
        os.environ.get("CAPSOLVER_PROXY", "").strip()
        or os.environ.get("FABLETICS_PROXY", "").strip()
    )
    if not raw:
        return None
    return parse_proxy(raw)


def _turnstile_page_url() -> str:
    return os.environ.get("TURNSTILE_PAGE_URL", TURNSTILE_PAGE_URL).strip()


def _turnstile_action() -> str:
    return os.environ.get("TURNSTILE_ACTION", TURNSTILE_ACTION).strip()


def _recaptcha_site_key() -> str:
    return os.environ.get("RECAPTCHA_SITE_KEY", RECAPTCHA_SITE_KEY).strip()


def _recaptcha_page_url() -> str:
    return os.environ.get("RECAPTCHA_PAGE_URL", f"{BASE_URL}/").strip()


def _recaptcha_action() -> str:
    return os.environ.get("RECAPTCHA_ACTION", RECAPTCHA_ACTION).strip()


def solve_turnstile(timeout: int = 120, proxy: str | None = None) -> str | None:
    """Solve Cloudflare Turnstile (what the Fabletics app uses on login)."""
    if _local_solver is not None:
        return _local_solver(min(timeout, 60))

    api_key = captcha_api_key()
    site_key = turnstile_site_key()
    if not api_key:
        return None
    if not site_key:
        raise RuntimeError("TURNSTILE_SITE_KEY is not configured")

    page_url = _turnstile_page_url()
    action = _turnstile_action()
    resolved_proxy = _solver_proxy(proxy)

    attempts: list[dict] = []
    metadata = {"action": action} if action else None
    if resolved_proxy:
        task: dict = {
            "type": "AntiTurnstileTask",
            "websiteURL": page_url,
            "websiteKey": site_key,
            "proxy": resolved_proxy,
        }
        if metadata:
            task["metadata"] = metadata
        attempts.append(task)
    else:
        task_proxyless: dict = {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        if metadata:
            task_proxyless["metadata"] = metadata
        attempts.append(task_proxyless)

    last_error: Exception | None = None
    for task in attempts:
        try:
            task_id = _create_task(api_key, task)
            return _poll_capsolver_task(api_key, task_id, timeout=timeout)
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return None


def solve_recaptcha(timeout: int = 120, proxy: str | None = None) -> str | None:
    """Legacy reCAPTCHA fallback (Fabletics login now uses Turnstile)."""
    api_key = captcha_api_key()
    if not api_key:
        return None

    page_url = _recaptcha_page_url()
    site_key = _recaptcha_site_key()
    action = _recaptcha_action()
    resolved_proxy = _solver_proxy(proxy)

    attempts: list[dict] = []
    if resolved_proxy:
        attempts.extend(
            [
                {
                    "type": "ReCaptchaV2Task",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "proxy": resolved_proxy,
                },
                {
                    "type": "ReCaptchaV3Task",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "pageAction": action,
                    "proxy": resolved_proxy,
                },
            ]
        )
    attempts.extend(
        [
            {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            },
            {
                "type": "ReCaptchaV3TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
                "pageAction": action,
            },
        ]
    )

    last_error: Exception | None = None
    for task in attempts:
        try:
            task_id = _create_task(api_key, task)
            return _poll_capsolver_task(api_key, task_id, timeout=timeout)
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return None


def solve_login_captcha(timeout: int = 120, proxy: str | None = None) -> str | None:
    """Solve the captcha token required for Fabletics login."""
    if turnstile_site_key():
        return solve_turnstile(timeout=timeout, proxy=proxy)
    return solve_recaptcha(timeout=timeout, proxy=proxy)


def get_capsolver_balance(force: bool = False) -> dict[str, Any]:
    """Return CapSolver account balance (USD), cached for 30s."""
    global _balance_cache, _balance_cache_at

    balance_key = _balance_api_key()
    if not balance_key:
        return {"configured": False, "balance": None, "error": None}

    now = time.time()
    if (
        not force
        and _balance_cache is not None
        and now - _balance_cache_at < _BALANCE_CACHE_TTL
    ):
        return _balance_cache

    payload: dict[str, Any]
    if _uses_local_solver():
        payload = {
            "configured": True,
            "balance": None,
            "error": None,
            "solver": "local-camoufox",
        }
        if balance_key.startswith("CAP-"):
            try:
                result = _capsolver_post(
                    _CLOUD_BALANCE_URL,
                    {"clientKey": balance_key},
                    timeout=10,
                )
                if not result.get("errorId"):
                    balance = result.get("balance")
                    payload["balance"] = float(balance) if balance is not None else None
                else:
                    payload["error"] = result.get("errorDescription")
            except Exception as exc:
                payload["error"] = str(exc)
        _balance_cache = payload
        _balance_cache_at = now
        return payload

    try:
        result = _capsolver_post(_balance_url(), {"clientKey": balance_key}, timeout=10)
        if result.get("errorId"):
            payload = {
                "configured": True,
                "balance": None,
                "error": result.get("errorDescription") or "CapSolver balance lookup failed",
            }
        else:
            balance = result.get("balance")
            payload = {
                "configured": True,
                "balance": float(balance) if balance is not None else None,
                "error": None,
            }
    except Exception as exc:
        payload = {
            "configured": True,
            "balance": _balance_cache.get("balance") if _balance_cache else None,
            "error": str(exc),
        }

    _balance_cache = payload
    _balance_cache_at = now
    return payload
