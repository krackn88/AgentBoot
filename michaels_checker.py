#!/usr/bin/env python3
"""
Michaels.com request checker powered by RiskByPass.

Runs each step of the sign-in and Michaels Rewards flow and reports pass/fail
with details. Uses RB for PerimeterX (and optional Akamai) bypass, curl_cffi for
TLS-impersonated HTTP, and RB tls_forward as POST fallback.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from curl_cffi import requests as cffi_requests

from rb_client import (
    RiskByPassClient,
    RiskByPassError,
    apply_rb_cookies,
    merge_cookies,
)

BASE = "https://www.michaels.com"
SIGNIN_URL = f"{BASE}/signin"
USER_API = f"{BASE}/api/usr"
RWD_API = f"{BASE}/api/rewards"

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
    """Accept host:port:user:pass or http://user:pass@host:port."""
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


def device_uuid() -> str:
    return str(uuid.uuid4())


def summarize_rewards(data: dict[str, Any]) -> dict[str, Any]:
    """Pull the high-value rewards fields from memberLookUp response."""
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
        px_app_id: str | None = None,
        px_attempts: int = 3,
        use_akamai: bool = True,
    ) -> None:
        self.rb = rb
        self.proxy = proxy
        self.proxy_dict = {"http": proxy, "https": proxy}
        self.email = email
        self.password = password
        self.px_app_id = px_app_id
        self.px_attempts = px_attempts
        self.use_akamai = use_akamai
        self.cookies: dict[str, str] = {}
        self.ua = DESKTOP_UA
        self.auth_token = ""
        self.loyalty_id: str | None = None
        self.device_uuid = device_uuid()

    def _session(self) -> cffi_requests.Session:
        s = cffi_requests.Session(impersonate="chrome131")
        s.headers.update(
            {
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Lang": "en_US",
                "Region": "US",
            }
        )
        for k, v in self.cookies.items():
            s.cookies.set(k, v, domain=".michaels.com")
        if self.auth_token:
            s.headers["Authorization"] = f"Bearer {self.auth_token}"
        return s

    def _apply_response_cookies(self, session: cffi_requests.Session) -> None:
        self.cookies.update(dict(session.cookies))

    def _apply_rb_result(self, result: dict[str, Any]) -> None:
        solved, ua = apply_rb_cookies(result)
        self.cookies = merge_cookies(self.cookies, solved)
        if ua:
            self.ua = ua

    def check_signin_page(self) -> CheckResult:
        name = "signin_page"
        try:
            s = self._session()
            s.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            r = s.get(SIGNIN_URL, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            blocked = r.status_code == 403 or "Access Denied" in r.text
            has_signin = "Sign In" in r.text or "signin" in r.text.lower()
            px_cookies = [k for k in self.cookies if k.startswith("_px")]
            return CheckResult(
                name=name,
                ok=r.status_code == 200 and has_signin and not blocked,
                status_code=r.status_code,
                detail=(
                    f"blocked={blocked} signin_text={has_signin} "
                    f"px_cookies={px_cookies or 'none'}"
                ),
                extra={"cookie_count": len(self.cookies)},
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_px_solve(self) -> CheckResult:
        name = "rb_perimeterx"
        last_error = ""
        solvers = [
            ("invisible", self.rb.perimeterx_invisible),
            ("hold", self.rb.perimeterx_hold),
        ]
        for attempt in range(1, self.px_attempts + 1):
            kind, solver = solvers[(attempt - 1) % len(solvers)]
            try:
                result = solver(
                    proxy=self.proxy,
                    target_url=SIGNIN_URL,
                    px_app_id=self.px_app_id,
                    init_cookies=self.cookies or None,
                )
                self._apply_rb_result(result)
                px_cookies = [k for k in self.cookies if k.startswith("_px")]
                if px_cookies:
                    return CheckResult(
                        name=name,
                        ok=True,
                        detail=f"{kind} solved on attempt {attempt}",
                        extra={"attempt": attempt, "px_cookies": px_cookies},
                    )
            except RiskByPassError as exc:
                last_error = str(exc)
                continue
        px_cookies = [k for k in self.cookies if k.startswith("_px")]
        return CheckResult(
            name=name,
            ok=bool(px_cookies),
            detail=last_error or f"best px_cookies={px_cookies or 'none'}",
            extra={"attempts": self.px_attempts, "px_cookies": px_cookies},
        )

    def check_akamai_solve(self) -> CheckResult:
        name = "rb_akamai"
        if not self.use_akamai:
            return CheckResult(name=name, ok=True, detail="skipped")
        last_error = ""
        try:
            s = self._session()
            s.headers["Accept"] = "text/html,*/*"
            r = s.get(SIGNIN_URL, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            js_urls = []
            for token in ('src="', "src='"):
                start = 0
                while True:
                    idx = r.text.find(token, start)
                    if idx == -1:
                        break
                    end = r.text.find(r.text[idx + len(token)], idx + len(token))
                    if end != -1:
                        url = r.text[idx + len(token) : end]
                        if "akamai" in url.lower() or "/akam/" in url or "akam/" in url:
                            if url.startswith("//"):
                                url = "https:" + url
                            js_urls.append(url)
                    start = idx + 1
            if not js_urls and "_abck" not in self.cookies:
                return CheckResult(name=name, ok=True, detail="no akamai script detected")
            for attempt, js_url in enumerate(js_urls[:3] or [""], start=1):
                if not js_url:
                    break
                try:
                    result = self.rb.akamai(
                        proxy=self.proxy,
                        target_url=SIGNIN_URL,
                        akamai_js_url=js_url,
                        init_cookies=self.cookies or None,
                    )
                    self._apply_rb_result(result)
                    if self.cookies.get("_abck"):
                        return CheckResult(
                            name=name,
                            ok=True,
                            detail=f"_abck set via attempt {attempt}",
                            extra={"js_url": js_url[:120]},
                        )
                except RiskByPassError as exc:
                    last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        has_abck = bool(self.cookies.get("_abck"))
        return CheckResult(
            name=name,
            ok=has_abck or not last_error,
            detail=last_error or f"_abck={'set' if has_abck else 'missing'}",
        )

    def _signin_body(self) -> dict[str, Any]:
        return {
            "deviceUuid": self.device_uuid,
            "deviceType": 0,
            "deviceName": "Chrome",
            "loginAddress": "",
            "emailPassword": {"email": self.email, "password": self.password},
            "rememberMe": True,
            "platform": "web",
        }

    def check_sign_in(self) -> CheckResult:
        name = "sign_in"
        if not self.email or not self.password:
            return CheckResult(name=name, ok=False, detail="credentials not configured")
        url = f"{USER_API}/user/sign-in-secure"
        body = self._signin_body()
        try:
            s = self._session()
            s.headers.update(
                {
                    "Origin": BASE,
                    "Referer": SIGNIN_URL,
                    "Content-Type": "application/json",
                }
            )
            r = s.post(url, json=body, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            if r.status_code in (403, 429):
                return self._tls_forward_check(name, url, "POST", body)
            if r.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=r.status_code,
                    detail=r.text[:300],
                )
            return self._parse_signin_response(name, r.json(), r.status_code)
        except Exception as exc:
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
            s = self._session()
            s.headers.update({"Referer": f"{BASE}/buyertools/rewards/my-rewards"})
            r = s.get(url, proxies=self.proxy_dict, timeout=30)
            if r.status_code in (403, 429):
                return self._tls_forward_check(name, url, "GET", None)
            if r.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=r.status_code,
                    detail=r.text[:200],
                )
            data = r.json()
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
        except Exception as exc:
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
            s = self._session()
            s.headers.update(
                {
                    "Origin": BASE,
                    "Referer": f"{BASE}/buyertools/rewards/my-rewards",
                    "Content-Type": "application/json",
                }
            )
            r = s.post(url, json=body, proxies=self.proxy_dict, timeout=30)
            if r.status_code in (403, 429):
                return self._tls_forward_check(name, url, "POST", body, parse_rewards=True)
            if r.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=r.status_code,
                    detail=r.text[:300],
                )
            data = r.json()
            summary = summarize_rewards(data.get("data", data))
            ok = bool(summary.get("availablePoints") is not None or summary.get("member") or summary)
            return CheckResult(
                name=name,
                ok=ok or bool(summary),
                status_code=200,
                detail=json.dumps(summary)[:500],
                extra={"rewards_summary": summary, "raw": data},
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def _tls_forward_check(
        self,
        name: str,
        url: str,
        method: str,
        body: dict[str, Any] | None,
        *,
        parse_rewards: bool = False,
    ) -> CheckResult:
        try:
            headers = {
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE,
                "Referer": SIGNIN_URL,
                "Content-Type": "application/json",
                "Lang": "en_US",
                "Region": "US",
            }
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            result = self.rb.tls_forward(
                proxy=self.proxy,
                target_url=url,
                method=method,
                headers=headers,
                cookies=self.cookies,
                ua=self.ua,
                body=json.dumps(body) if body is not None else None,
            )
            status = result.get("status_code")
            raw = ""
            if result.get("body_base64"):
                raw = base64.b64decode(result["body_base64"]).decode("utf-8", "replace")
            if status == 200 and raw.startswith("{"):
                data = json.loads(raw)
                if parse_rewards:
                    summary = summarize_rewards(data.get("data", data))
                    return CheckResult(
                        name=name,
                        ok=bool(summary),
                        status_code=status,
                        detail=json.dumps(summary)[:500],
                        extra={"rewards_summary": summary, "raw": data},
                    )
                if "sign_in" in name or "token" in raw:
                    return self._parse_signin_response(name, data, status)
                payload = data.get("data") or data
                loyalty_id = payload if isinstance(payload, str) else payload.get("loyaltyId")
                if loyalty_id:
                    self.loyalty_id = str(loyalty_id)
                return CheckResult(
                    name=name,
                    ok=bool(loyalty_id),
                    status_code=status,
                    detail=f"tls_forward loyaltyId={loyalty_id}",
                )
            return CheckResult(
                name=name,
                ok=False,
                status_code=status,
                detail=f"tls_forward: {raw[:200]}",
            )
        except RiskByPassError as exc:
            return CheckResult(name=name, ok=False, detail=f"tls_forward failed: {exc}")

    def run(self) -> CheckerReport:
        report = CheckerReport(proxy=self.proxy, cookies=self.cookies)

        report.add(self.check_signin_page())
        report.add(self.check_px_solve())
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
    parser.add_argument("--token", default=os.environ.get("RB_TOKEN", ""), help="RiskByPass API token")
    parser.add_argument(
        "--proxy",
        default=os.environ.get("RB_PROXY", ""),
        help="Proxy (URL or host:port:user:pass)",
    )
    parser.add_argument("--email", default=os.environ.get("MICHAELS_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("MICHAELS_PASSWORD", ""))
    parser.add_argument("--px-app-id", default=os.environ.get("MICHAELS_PX_APP_ID", ""))
    parser.add_argument("--px-attempts", type=int, default=3)
    parser.add_argument("--no-akamai", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args()

    if not args.token:
        print("error: RB_TOKEN / --token required", file=sys.stderr)
        return 2
    if not args.proxy:
        print("error: RB_PROXY / --proxy required", file=sys.stderr)
        return 2

    proxy = parse_proxy(args.proxy)
    rb = RiskByPassClient(token=args.token)
    checker = MichaelsChecker(
        rb,
        proxy,
        email=args.email,
        password=args.password,
        px_app_id=args.px_app_id or None,
        px_attempts=args.px_attempts,
        use_akamai=not args.no_akamai,
    )
    report = checker.run()

    if args.json_out:
        payload = report.to_dict()
        if report.rewards is None and any(
            r.extra.get("rewards_summary") for r in report.results
        ):
            for r in report.results:
                if r.extra.get("rewards_summary"):
                    payload["rewards"] = r.extra["rewards_summary"]
        print(json.dumps(payload, indent=2))
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
