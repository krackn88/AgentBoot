#!/usr/bin/env python3
"""
Bloomingdale's request checker powered by RiskByPass.

Runs each API step in the login / loyalty flow and reports pass/fail with
details. Uses RB for Akamai _abck generation (and optional reCAPTCHA v3),
curl_cffi for TLS-impersonated HTTP, and RB tls_forward as POST fallback.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from curl_cffi import requests as cffi_requests

from rb_client import RiskByPassClient, RiskByPassError, abck_trust_segment, merge_cookies

# Akamai script URLs observed on sign-in / shop pages
AKAMAI_JS_URLS = [
    "https://www.bloomingdales.com/g_Ywhy/XL2_/zlLc/jbYQ/PhxLGj/X5iDXmkOuOu90bQOiV/QysCRnJjBw/S1NZ/OzQZbT0B",
    "https://www.bloomingdales.com/g_Ywhy/XL2_/zlLc/jbYQ/PhxLGj/VViDEJ/C19aRXJjBw/AjIS/PWoqN0cp",
]

DEFAULT_PAGE_FP = (
    "42455e5a4e495c515f4541595f465355405a435f5f585f5b4e495c53464b4a45"
    "405a435f5f585f5b4e495c53464b4a455f534650455f455f534646415f4e495c53"
    "464b4a455f534650455f455f534646415f4e495c53464b4a455f534650455f455f"
)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
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
    site: str = "bloomingdales.com"
    proxy: str = ""
    results: list[CheckResult] = field(default_factory=list)
    cookies: dict[str, str] = field(default_factory=dict)
    signed_in: bool = False
    loyalty: dict[str, Any] | None = None

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
            "loyalty": self.loyalty,
            "results": [asdict(r) for r in self.results],
        }


class BloomingdalesChecker:
    def __init__(
        self,
        rb: RiskByPassClient,
        proxy: str,
        email: str = "",
        password: str = "",
        *,
        akamai_attempts: int = 5,
        use_captcha: bool = True,
    ) -> None:
        self.rb = rb
        self.proxy = proxy
        self.proxy_dict = {"http": proxy, "https": proxy}
        self.email = email
        self.password = password
        self.akamai_attempts = akamai_attempts
        self.use_captcha = use_captcha
        self.cookies: dict[str, str] = {}
        self.ua = DESKTOP_UA
        self.pattern = "2,7,14,15,16"
        self.recaptcha_site_key: str | None = None

    def _session(self, mobile: bool = False) -> cffi_requests.Session:
        s = cffi_requests.Session(impersonate="chrome131")
        s.headers.update(
            {
                "User-Agent": MOBILE_UA if mobile else self.ua,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        for k, v in self.cookies.items():
            s.cookies.set(k, v, domain=".bloomingdales.com")
        return s

    def _apply_response_cookies(self, session: cffi_requests.Session) -> None:
        self.cookies.update(dict(session.cookies))

    def _device_fingerprint(self) -> str:
        raw = f"{self.pattern}|{random.randint(100000, 999999)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _metadata(self) -> str:
        parts = self.pattern.replace("16", "").split(",")
        return "_".join(p for p in parts if p in ("2", "7", "14", "15")) or "2_7_14_15"

    def check_signin_page(self, base: str, mobile: bool) -> CheckResult:
        name = f"signin_page ({'mobile' if mobile else 'desktop'})"
        try:
            s = self._session(mobile=mobile)
            s.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            r = s.get(f"{base}/account/signin", proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            ok = r.status_code == 200 and "Sign In" in r.text
            seg = abck_trust_segment(self.cookies)
            return CheckResult(
                name=name,
                ok=ok,
                status_code=r.status_code,
                detail=f"title_ok={ok} _abck_segment={seg}",
                extra={"cookie_count": len(self.cookies)},
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_akamai_solve(self, target_url: str) -> CheckResult:
        name = "rb_akamai"
        last_error = ""
        for attempt in range(1, self.akamai_attempts + 1):
            js_url = AKAMAI_JS_URLS[(attempt - 1) % len(AKAMAI_JS_URLS)]
            try:
                result = self.rb.akamai(
                    proxy=self.proxy,
                    target_url=target_url,
                    akamai_js_url=js_url,
                    init_cookies=self.cookies or None,
                    page_fp=DEFAULT_PAGE_FP,
                )
                solved = result.get("cookies_dict") or result.get("cookies") or {}
                self.cookies = merge_cookies(self.cookies, solved)
                self.ua = result.get("ua") or self.ua
                seg = abck_trust_segment(self.cookies)
                if seg == "0":
                    return CheckResult(
                        name=name,
                        ok=True,
                        detail=f"trusted _abck after attempt {attempt}",
                        extra={"attempt": attempt, "abck_segment": seg},
                    )
            except RiskByPassError as exc:
                last_error = str(exc)
                continue
        seg = abck_trust_segment(self.cookies)
        return CheckResult(
            name=name,
            ok=seg == "0",
            detail=last_error or f"best _abck_segment={seg} after {self.akamai_attempts} attempts",
            extra={"abck_segment": seg, "attempts": self.akamai_attempts},
        )

    def check_pre_signin(self, base: str, device: str) -> CheckResult:
        name = f"pre_signin ({device})"
        url = f"{base}/account-xapi/api/account/signin?_deviceType={device}"
        try:
            s = self._session(mobile=(device == "Phone"))
            s.headers.update(
                {
                    "Origin": base,
                    "Referer": f"{base}/account/signin",
                    "Cache-Control": "no-cache",
                }
            )
            r = s.get(url, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            if r.status_code != 200:
                return CheckResult(name=name, ok=False, status_code=r.status_code, detail=r.text[:200])
            data = r.json()
            user = data.get("user", {})
            self.pattern = user.get("pattern", self.pattern)
            self.recaptcha_site_key = user.get("googleRecaptchaLoginSiteKey")
            for c in user.get("cookies", []):
                if c.get("name"):
                    self.cookies[c["name"]] = c["value"]
            return CheckResult(
                name=name,
                ok=True,
                status_code=200,
                detail=f"pattern={self.pattern} captcha_enabled={user.get('killswitches', {}).get('signInCaptchaEnabled')}",
                extra={"guid": user.get("guid"), "recaptcha_key": self.recaptcha_site_key},
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_email_verify(self, base: str, device: str) -> CheckResult:
        name = f"email_verify ({device})"
        if not self.email:
            return CheckResult(name=name, ok=False, detail="email not configured")
        url = f"{base}/account-xapi/api/myaccount/email?_deviceType={device}"
        body = {"user": {"email": self.email}}
        try:
            s = self._session(mobile=(device == "Phone"))
            s.headers.update(
                {
                    "Origin": base,
                    "Referer": f"{base}/account/signin",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
            r = s.post(url, json=body, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            if r.status_code == 200:
                data = r.json()
                user = data.get("user", {})
                return CheckResult(
                    name=name,
                    ok=True,
                    status_code=200,
                    detail=f"softProfile={user.get('softProfileFlag')} error={user.get('error')}",
                )
            if r.status_code == 403:
                return self._tls_forward_check(
                    name, url, "POST", body, base, device, fallback_detail=r.text[:120]
                )
            return CheckResult(name=name, ok=False, status_code=r.status_code, detail=r.text[:200])
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_sign_in(self, base: str, device: str, captcha_token: str | None) -> CheckResult:
        name = f"sign_in ({device})"
        if not self.email or not self.password:
            return CheckResult(name=name, ok=False, detail="credentials not configured")
        url = f"{base}/account-xapi/api/account/signin?_deviceType={device}"
        dfp = self._device_fingerprint()
        signin: dict[str, Any] = {
            "email": self.email,
            "password": self.password,
            "keepMeSignedIn": True,
            "metaData": self._metadata(),
            "deviceFingerPrint": dfp,
        }
        if captcha_token:
            signin["captchaResp"] = captcha_token
        body = {"SignIn": signin}
        try:
            s = self._session(mobile=(device == "Phone"))
            s.headers.update(
                {
                    "Origin": base,
                    "Referer": f"{base}/account/signin",
                    "Content-Type": "application/json",
                    "X-Macys-DeviceFingerprint": dfp,
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
            r = s.post(url, json=body, proxies=self.proxy_dict, timeout=30)
            self._apply_response_cookies(s)
            if r.status_code == 403:
                return self._tls_forward_check(
                    name,
                    url,
                    "POST",
                    body,
                    base,
                    device,
                    dfp=dfp,
                    fallback_detail="curl_cffi 403",
                )
            if r.status_code != 200:
                return CheckResult(name=name, ok=False, status_code=r.status_code, detail=r.text[:200])
            return self._parse_signin_response(name, r.json(), r.status_code)
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def check_loyalty(self) -> CheckResult:
        name = "loyalty_accountsummary"
        url = "https://www.bloomingdales.com/xapi/loyalty/v1/accountsummary?_pageType=myAccount"
        try:
            s = self._session()
            s.headers.update(
                {
                    "Referer": "https://www.bloomingdales.com/account/myaccount",
                    "Accept": "application/json",
                }
            )
            r = s.get(url, proxies=self.proxy_dict, timeout=30)
            if r.status_code != 200:
                return CheckResult(
                    name=name,
                    ok=False,
                    status_code=r.status_code,
                    detail=r.text[:300],
                )
            data = r.json()
            return CheckResult(
                name=name,
                ok=True,
                status_code=200,
                detail="loyalty summary retrieved",
                extra={"summary": data},
            )
        except Exception as exc:
            return CheckResult(name=name, ok=False, detail=str(exc))

    def _parse_signin_response(
        self, name: str, data: dict[str, Any], status_code: int
    ) -> CheckResult:
        user = data.get("user", {})
        if user.get("error"):
            err = user["error"]
            return CheckResult(
                name=name,
                ok=False,
                status_code=status_code,
                detail=f"errorCode={err.get('errorCode')} message={err.get('message', '')[:120]}",
            )
        signed_in = user.get("firstName") or user.get("userId")
        for c in user.get("cookies", []):
            if c.get("name"):
                self.cookies[c["name"]] = c["value"]
        signed_cookie = any(
            c.get("name") == "SignedIn" and c.get("value") == "1"
            for c in user.get("cookies", [])
        )
        ok = bool(signed_in or signed_cookie)
        return CheckResult(
            name=name,
            ok=ok,
            status_code=status_code,
            detail=f"firstName={user.get('firstName')} userId={user.get('userId')} SignedIn={signed_cookie}",
            extra={"user": {k: user.get(k) for k in ("firstName", "userId", "lastName")}},
        )

    def _tls_forward_check(
        self,
        name: str,
        url: str,
        method: str,
        body: dict[str, Any],
        base: str,
        device: str,
        *,
        dfp: str | None = None,
        fallback_detail: str = "",
    ) -> CheckResult:
        try:
            headers = {
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Origin": base,
                "Referer": f"{base}/account/signin",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }
            if dfp:
                headers["X-Macys-DeviceFingerprint"] = dfp
            if method.upper() == "POST":
                resp = self.rb.tls_post(
                    url,
                    proxy=self.proxy,
                    headers=headers,
                    cookies=self.cookies,
                    body=body,
                )
            else:
                resp = self.rb.tls_get(
                    url,
                    proxy=self.proxy,
                    headers=headers,
                    cookies=self.cookies,
                )
            status = resp.status_code
            raw = resp.text
            if status == 200 and raw.startswith("{"):
                return self._parse_signin_response(name, json.loads(raw), status)
            return CheckResult(
                name=name,
                ok=False,
                status_code=status,
                detail=f"tls_forward: {raw[:200] or fallback_detail}",
            )
        except RiskByPassError as exc:
            return CheckResult(name=name, ok=False, detail=f"tls_forward failed: {exc}")

    def run(self, profile: str = "desktop") -> CheckerReport:
        report = CheckerReport(proxy=self.proxy, cookies=self.cookies)

        if profile in ("desktop", "both"):
            base = "https://www.bloomingdales.com"
            report.add(self.check_signin_page(base, mobile=False))
            report.add(self.check_akamai_solve(f"{base}/account/signin"))
            report.add(self.check_pre_signin(base, "PC"))
            report.add(self.check_email_verify(base, "PC"))

            captcha_token = None
            if self.use_captcha and self.recaptcha_site_key:
                try:
                    captcha_token = self.rb.recaptcha_v3(
                        proxy=self.proxy,
                        site_key=self.recaptcha_site_key,
                        target_url=f"{base}/account/signin",
                    )
                    report.add(
                        CheckResult(
                            name="rb_recaptcha_v3",
                            ok=True,
                            detail=f"token_len={len(captcha_token)}",
                        )
                    )
                except RiskByPassError as exc:
                    report.add(
                        CheckResult(name="rb_recaptcha_v3", ok=False, detail=str(exc))
                    )

            signin_result = self.check_sign_in(base, "PC", captcha_token)
            report.add(signin_result)
            report.signed_in = signin_result.ok

        if profile in ("mobile", "both"):
            base = "https://m.bloomingdales.com"
            report.add(self.check_signin_page(base, mobile=True))
            report.add(self.check_pre_signin(base, "Phone"))
            report.add(self.check_email_verify(base, "Phone"))

            captcha_token = None
            if self.use_captcha and self.recaptcha_site_key:
                try:
                    captcha_token = self.rb.recaptcha_v3(
                        proxy=self.proxy,
                        site_key=self.recaptcha_site_key or "6LeBmfQbAAAAAP4QMXwFhljA4MZme6xEJJh3rGxT",
                        target_url=f"{base}/account/signin",
                    )
                    report.add(
                        CheckResult(
                            name="rb_recaptcha_v3 (mobile)",
                            ok=True,
                            detail=f"token_len={len(captcha_token)}",
                        )
                    )
                except RiskByPassError as exc:
                    report.add(
                        CheckResult(
                            name="rb_recaptcha_v3 (mobile)", ok=False, detail=str(exc)
                        )
                    )

            signin_result = self.check_sign_in(base, "Phone", captcha_token)
            report.add(signin_result)
            report.signed_in = report.signed_in or signin_result.ok

        loyalty_result = self.check_loyalty()
        report.add(loyalty_result)
        if loyalty_result.ok and loyalty_result.extra.get("summary"):
            report.loyalty = loyalty_result.extra["summary"]

        report.cookies = self.cookies
        return report


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloomingdale's RB request checker")
    parser.add_argument("--token", default=os.environ.get("RB_TOKEN", ""), help="RiskByPass API token")
    parser.add_argument("--proxy", default=os.environ.get("RB_PROXY", ""), help="Proxy (URL or host:port:user:pass)")
    parser.add_argument("--email", default=os.environ.get("BLOOMINGDALES_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("BLOOMINGDALES_PASSWORD", ""))
    parser.add_argument(
        "--profile",
        choices=("desktop", "mobile", "both"),
        default="both",
        help="Which endpoint profile to test",
    )
    parser.add_argument("--akamai-attempts", type=int, default=5)
    parser.add_argument("--no-captcha", action="store_true")
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
    checker = BloomingdalesChecker(
        rb,
        proxy,
        email=args.email,
        password=args.password,
        akamai_attempts=args.akamai_attempts,
        use_captcha=not args.no_captcha,
    )
    report = checker.run(profile=args.profile)

    if args.json_out:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Bloomingdale's Request Checker  proxy={proxy.split('@')[-1]}")
        print("-" * 60)
        for r in report.results:
            mark = "PASS" if r.ok else "FAIL"
            code = f" [{r.status_code}]" if r.status_code else ""
            print(f"{mark}  {r.name}{code}")
            if r.detail:
                print(f"       {r.detail}")
        print("-" * 60)
        print(f"signed_in={report.signed_in}  all_checks_ok={report.all_ok}")
        if report.loyalty:
            print(f"loyalty={json.dumps(report.loyalty)[:500]}")

    return 0 if report.signed_in else 1


if __name__ == "__main__":
    sys.exit(main())
