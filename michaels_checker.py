#!/usr/bin/env python3
"""
Michaels.com request checker powered by RiskByPass.

Flow (matches RB official akamai demos):
  1. curl_cffi GET /signin  -> init cookies + fresh akamai JS URL
  2. RB akamai (with page_fp) -> trusted _abck segment 0
  3. RB tls_forward for all API calls (sign-in, loyalty, rewards)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from curl_cffi import requests as cffi_requests

from rb_client import (
    RiskByPassClient,
    RiskByPassError,
    TlsResponse,
    abck_trust_segment,
    apply_rb_cookies,
    merge_cookies,
)

BASE = "https://www.michaels.com"
SIGNIN_URL = f"{BASE}/signin"
USER_API = f"{BASE}/api/usr"
RWD_API = f"{BASE}/api/rewards"
REWARDS_REFERER = f"{BASE}/buyertools/rewards/my-rewards"

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int | None = None
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckerReport:
    site: str = "michaels.com"
    proxy: str = ""
    results: list[CheckResult] = field(default_factory=list)
    cookies: dict[str, str] = field(default_factory=dict)
    signed_in: bool = False
    auth_token: str = ""
    loyalty_id: str | None = None
    rewards: dict[str, Any] | None = None

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "proxy": self.proxy,
            "signed_in": self.signed_in,
            "all_ok": self.all_ok,
            "auth_token_set": bool(self.auth_token),
            "loyalty_id": self.loyalty_id,
            "rewards": self.rewards,
            "results": [asdict(r) for r in self.results],
        }


def parse_proxy(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    raise ValueError(f"Invalid proxy format: {raw!r}")


def scrape_akamai_js_urls(html: str) -> list[str]:
    urls = re.findall(r"https://www\.michaels\.com/akam/[^\"'\s>]+", html)
    return [u for u in urls if "pixel_" not in u]


def summarize_rewards(data: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    members = data.get("member") or data.get("data", {}).get("member") or []
    if isinstance(members, list) and members:
        member = members[0]
        for key in (
            "loyaltyId",
            "availablePoints",
            "pendingPoints",
            "totalPoints",
            "pointsBalance",
            "rewardBalance",
            "tierStatus",
            "tierName",
            "firstName",
            "lastName",
            "email",
            "phoneNo",
            "loyaltySegments",
        ):
            if key in member and member[key] not in (None, ""):
                summary[key] = member[key]

    points_history = data.get("RewardPointsHistory") or data.get("data", {}).get(
        "RewardPointsHistory"
    )
    if points_history:
        summary["points_history_count"] = len(points_history)

    vouchers = data.get("vouchers") or data.get("data", {}).get("vouchers")
    if vouchers:
        summary["vouchers_count"] = len(vouchers)
        summary["vouchers"] = [
            {
                "card_number": v.get("card_number"),
                "balance": v.get("balance"),
                "appliedAmount": v.get("appliedAmount"),
            }
            for v in vouchers[:5]
        ]

    offers = data.get("CRMOffers") or data.get("data", {}).get("CRMOffers")
    if offers:
        summary["crm_offers_count"] = len(offers)

    if not summary:
        summary["raw_keys"] = list(data.keys())
    return summary


class MichaelsChecker:
    def __init__(
        self,
        rb: RiskByPassClient,
        proxy: str,
        email: str = "",
        password: str = "",
        *,
        akamai_attempts: int = 10,
    ) -> None:
        self.rb = rb
        self.proxy = proxy
        self.proxy_dict = {"http": proxy, "https": proxy}
        self.email = email
        self.password = password
        self.akamai_attempts = akamai_attempts
        self.cookies: dict[str, str] = {}
        self.ua = DESKTOP_UA
        self.auth_token = ""
        self.loyalty_id: str | None = None
        self.device_uuid = str(uuid.uuid4())
        self.akamai_js_urls: list[str] = []

    def _api_headers(self, *, referer: str = SIGNIN_URL, auth: bool = False) -> dict[str, str]:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": BASE,
            "referer": referer,
            "lang": "en_US",
            "region": "US",
            "user-agent": self.ua,
        }
        if auth and self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _merge_tls_cookies(self, resp: TlsResponse) -> None:
        if resp.cookies:
            self.cookies = merge_cookies(self.cookies, resp.cookies)

    def check_signin_page(self) -> CheckResult:
        name = "signin_page"
        try:
            s = cffi_requests.Session(impersonate="chrome131")
            s.headers.update(
                {
                    "User-Agent": self.ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )
            r = s.get(SIGNIN_URL, proxies=self.proxy_dict, timeout=30)
            self.cookies = dict(s.cookies)
            self.akamai_js_urls = scrape_akamai_js_urls(r.text)
            seg = abck_trust_segment(self.cookies)
            blocked = r.status_code == 403 or "Access Denied" in r.text
            has_signin = "Sign In" in r.text or "signin" in r.text.lower()
            return CheckResult(
                name=name,
                ok=r.status_code == 200 and has_signin and not blocked,
                status_code=r.status_code,
                detail=(
                    f"_abck_segment={seg} akamai_js={self.akamai_js_urls[:1]} "
                    f"cookies={list(self.cookies.keys())}"
                ),
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_akamai_solve(self) -> CheckResult:
        name = "rb_akamai"
        if not self.akamai_js_urls:
            return CheckResult(name=name, ok=False, detail="no akamai JS URL found on signin page")
        last_error = ""
        for attempt in range(1, self.akamai_attempts + 1):
            js_url = self.akamai_js_urls[(attempt - 1) % len(self.akamai_js_urls)]
            try:
                result = self.rb.akamai(
                    proxy=self.proxy,
                    target_url=SIGNIN_URL,
                    akamai_js_url=js_url,
                    init_cookies=self.cookies,
                )
                solved, ua = apply_rb_cookies(result)
                self.cookies = merge_cookies(self.cookies, solved)
                if ua:
                    self.ua = ua
                seg = abck_trust_segment(self.cookies)
                if seg == "0":
                    return CheckResult(
                        name=name,
                        ok=True,
                        detail=f"trusted _abck on attempt {attempt}",
                        extra={"attempt": attempt, "abck_segment": seg, "js_url": js_url},
                    )
                last_error = f"_abck_segment={seg} after attempt {attempt}"
            except RiskByPassError as exc:
                last_error = str(exc)
        seg = abck_trust_segment(self.cookies)
        return CheckResult(
            name=name,
            ok=seg == "0",
            detail=last_error or f"best _abck_segment={seg}",
            extra={"abck_segment": seg, "attempts": self.akamai_attempts},
        )

    def check_sign_in(self) -> CheckResult:
        name = "sign_in"
        if not self.email or not self.password:
            return CheckResult(name=name, ok=False, detail="credentials not configured")
        url = f"{USER_API}/user/sign-in-secure"
        body = {
            "deviceUuid": self.device_uuid,
            "deviceType": 0,
            "deviceName": "Chrome",
            "loginAddress": "",
            "emailPassword": {"email": self.email, "password": self.password},
            "rememberMe": True,
            "platform": "web",
        }
        try:
            resp = self.rb.tls_post(
                url,
                proxy=self.proxy,
                headers=self._api_headers(),
                cookies=self.cookies,
                body=body,
            )
            self._merge_tls_cookies(resp)
            if resp.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=resp.status_code,
                    detail=resp.text[:300],
                )
            return self._parse_signin_response(name, resp.json(), resp.status_code)
        except (RiskByPassError, json.JSONDecodeError, Exception) as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def _parse_signin_response(
        self, name: str, data: dict[str, Any], status_code: int
    ) -> CheckResult:
        payload = data.get("data") or data
        token = payload.get("token")
        user = payload.get("user") or {}
        if token:
            self.auth_token = token
        if payload.get("requireTwoFactorAuth"):
            return CheckResult(
                name=name,
                ok=False,
                status_code=status_code,
                detail="two-factor auth required",
                extra={"two_factor": True},
            )
        signed_in = bool(token and user)
        if user.get("loyaltyId"):
            self.loyalty_id = str(user["loyaltyId"])
        return CheckResult(
            name=name,
            ok=signed_in,
            status_code=status_code,
            detail=(
                f"user_id={user.get('id')} email={user.get('email')} "
                f"loyaltyId={user.get('loyaltyId')}"
            ),
            extra={
                "user": {
                    k: user.get(k)
                    for k in ("id", "email", "firstName", "lastName", "loyaltyId")
                }
            },
        )

    def check_loyalty_id(self) -> CheckResult:
        name = "loyalty_id"
        if not self.auth_token:
            return CheckResult(name=name, ok=False, detail="not authenticated")
        url = f"{RWD_API}/loyalty/findLoyaltyIdByUserId"
        try:
            resp = self.rb.tls_get(
                url,
                proxy=self.proxy,
                headers=self._api_headers(referer=REWARDS_REFERER, auth=True),
                cookies=self.cookies,
            )
            self._merge_tls_cookies(resp)
            if resp.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=resp.status_code,
                    detail=resp.text[:200],
                )
            data = resp.json()
            loyalty_id = data.get("data") or data.get("loyaltyId")
            if isinstance(loyalty_id, dict):
                loyalty_id = loyalty_id.get("loyaltyId") or loyalty_id.get("data")
            if loyalty_id:
                self.loyalty_id = str(loyalty_id)
            return CheckResult(
                name=name,
                ok=bool(self.loyalty_id),
                status_code=200,
                detail=f"loyaltyId={self.loyalty_id}",
            )
        except (RiskByPassError, json.JSONDecodeError, Exception) as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_rewards(self) -> CheckResult:
        name = "rewards_member_lookup"
        if not self.auth_token:
            return CheckResult(name=name, ok=False, detail="not authenticated")
        if not self.loyalty_id:
            return CheckResult(name=name, ok=False, detail="loyaltyId missing")
        url = f"{RWD_API}/direct/loyalty/memberLookUp"
        body = {
            "loyaltyId": self.loyalty_id,
            "emailId": self.email,
            "phoneNo": "",
            "division": "",
            "company": "MIK",
            "source": "ECOM",
            "getProfile": True,
            "getPointsHistory": True,
            "getTaxExemptInfo": True,
            "getCRMOffers": True,
            "getVouchers": True,
        }
        try:
            resp = self.rb.tls_post(
                url,
                proxy=self.proxy,
                headers=self._api_headers(referer=REWARDS_REFERER, auth=True),
                cookies=self.cookies,
                body=body,
            )
            self._merge_tls_cookies(resp)
            if resp.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=resp.status_code,
                    detail=resp.text[:300],
                )
            data = resp.json()
            summary = summarize_rewards(data.get("data", data))
            return CheckResult(
                name=name,
                ok=bool(summary),
                status_code=200,
                detail=json.dumps(summary)[:500],
                extra={"rewards_summary": summary, "raw": data},
            )
        except (RiskByPassError, json.JSONDecodeError, Exception) as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def run(self) -> CheckerReport:
        report = CheckerReport(proxy=self.proxy, cookies=self.cookies)

        report.add(self.check_signin_page())
        report.add(self.check_akamai_solve())

        signin_result = self.check_sign_in()
        report.add(signin_result)
        report.signed_in = signin_result.ok
        report.auth_token = self.auth_token

        if self.auth_token:
            loyalty_result = self.check_loyalty_id()
            report.add(loyalty_result)
            report.loyalty_id = self.loyalty_id

            rewards_result = self.check_rewards()
            report.add(rewards_result)
            if rewards_result.extra.get("rewards_summary"):
                report.rewards = rewards_result.extra["rewards_summary"]

        report.cookies = self.cookies
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Michaels RB request checker")
    parser.add_argument("--token", default=os.environ.get("RB_TOKEN", ""))
    parser.add_argument("--proxy", default=os.environ.get("RB_PROXY", ""))
    parser.add_argument("--email", default=os.environ.get("MICHAELS_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("MICHAELS_PASSWORD", ""))
    parser.add_argument("--akamai-attempts", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args()

    if not args.token:
        print("error: RB_TOKEN / --token required", file=sys.stderr)
        return 2
    if not args.proxy:
        print("error: RB_PROXY / --proxy required", file=sys.stderr)
        return 2

    proxy = parse_proxy(args.proxy)
    rb = RiskByPassClient(token=args.token, timeout=180)
    checker = MichaelsChecker(
        rb,
        proxy,
        email=args.email,
        password=args.password,
        akamai_attempts=args.akamai_attempts,
    )
    report = checker.run()

    if args.json_out:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Michaels Request Checker  proxy={proxy.split('@')[-1]}")
        print("-" * 60)
        for r in report.results:
            mark = "PASS" if r.ok else "FAIL"
            code = f" [{r.status_code}]" if r.status_code else ""
            print(f"{mark}  {r.name}{code}")
            if r.detail:
                print(f"       {r.detail}")
        print("-" * 60)
        print(f"signed_in={report.signed_in}  loyalty_id={report.loyalty_id}")
        if report.rewards:
            print(f"rewards={json.dumps(report.rewards)}")

    return 0 if report.signed_in and report.rewards else 1


if __name__ == "__main__":
    sys.exit(main())
