"""RiskByPass API client for akamai, recaptcha, and tls_forward tasks."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE_URL = "https://riskbypass.com"
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_TIMEOUT = 180

# page_fp used by RB akamai demos (kohls, bloomingdales, etc.)
DEFAULT_PAGE_FP = (
    "42455e5a4e495c515f4541595f465355405a435f5f585f5b4e495c53464b4a45"
    "405a435f5f585f5b4e495c53464b4a455f534650455f455f534646415f4e495c53"
    "464b4a455f534650455f455f534646415f4e495c53464b4a455f534650455f455f"
)


class RiskByPassError(Exception):
    """Raised when an RB task fails or times out."""


@dataclass
class TlsResponse:
    status_code: int
    text: str
    headers: dict[str, Any]
    cookies: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.text)


class RiskByPassClient:
    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "x-api-key": token}
        )

    def submit(self, payload: dict[str, Any]) -> str:
        resp = self.session.post(
            f"{self.base_url}/task/submit", json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RiskByPassError(f"No task_id in response: {data}")
        return task_id

    def poll(self, task_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            resp = self.session.get(
                f"{self.base_url}/task/result/{task_id}", timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or "").upper()
            if status in ("SUCCESS", "FAILED"):
                return data
            time.sleep(self.poll_interval)
        raise RiskByPassError(f"Task {task_id} timed out after {self.timeout}s")

    def run_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = self.submit(payload)
        data = self.poll(task_id)
        if data.get("status") != "SUCCESS":
            raise RiskByPassError(data.get("error") or data)
        return data.get("result") or data

    def akamai(
        self,
        *,
        proxy: str,
        target_url: str,
        akamai_js_url: str,
        init_cookies: dict[str, str] | None = None,
        page_fp: str | None = DEFAULT_PAGE_FP,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_type": "akamai",
            "proxy": proxy,
            "target_url": target_url,
            "akamai_js_url": akamai_js_url,
            "page_fp": page_fp or DEFAULT_PAGE_FP,
        }
        if init_cookies:
            payload["init_cookies"] = init_cookies
        return self.run_task(payload)

    def recaptcha_v3(
        self,
        *,
        proxy: str,
        site_key: str,
        target_url: str,
        action: str = "login",
        enterprise: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "task_type": "recaptchav3",
            "proxy": proxy,
            "site_key": site_key,
            "target_url": target_url,
            "action": action,
        }
        if enterprise:
            payload["enterprise"] = True
        result = self.run_task(payload)
        token = result.get("token") or result.get("gRecaptchaResponse")
        if not token:
            raise RiskByPassError(f"No captcha token in result: {result}")
        return token

    def tls_forward(
        self,
        *,
        proxy: str,
        url: str,
        method: str,
        headers: dict[str, str],
        cookies: dict[str, str],
        body: str | None = None,
        timeout: int = 60,
    ) -> TlsResponse:
        payload: dict[str, Any] = {
            "task_type": "tls_forward",
            "proxy": proxy,
            "url": url,
            "method": method.upper(),
            "headers": headers,
            "cookies_dict": cookies,
            "timeout": timeout,
        }
        if body is not None:
            payload["body_base64"] = base64.b64encode(body.encode()).decode()
        ua = headers.get("User-Agent") or headers.get("user-agent")
        if ua:
            payload["user_agent"] = ua
        result = self.run_task(payload)
        return parse_tls_result(result)

    def tls_get(
        self,
        url: str,
        *,
        proxy: str,
        headers: dict[str, str],
        cookies: dict[str, str],
        timeout: int = 60,
    ) -> TlsResponse:
        return self.tls_forward(
            proxy=proxy,
            url=url,
            method="GET",
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def tls_post(
        self,
        url: str,
        *,
        proxy: str,
        headers: dict[str, str],
        cookies: dict[str, str],
        body: dict[str, Any] | str,
        timeout: int = 60,
    ) -> TlsResponse:
        payload = body if isinstance(body, str) else json.dumps(body)
        return self.tls_forward(
            proxy=proxy,
            url=url,
            method="POST",
            headers=headers,
            cookies=cookies,
            body=payload,
            timeout=timeout,
        )


def parse_tls_result(result: dict[str, Any]) -> TlsResponse:
    text = result.get("text") or ""
    if not text and result.get("body_base64"):
        text = base64.b64decode(result["body_base64"]).decode("utf-8", "replace")
    cookies = result.get("cookies") or result.get("cookies_dict") or {}
    if isinstance(cookies, list):
        cookies = {c["name"]: c["value"] for c in cookies if c.get("name")}
    return TlsResponse(
        status_code=int(result.get("status_code") or 0),
        text=text,
        headers=result.get("headers") or {},
        cookies=cookies,
    )


def abck_trust_segment(cookies: dict[str, str]) -> str:
    abck = cookies.get("_abck", "")
    if "~" not in abck:
        return "missing"
    return abck.split("~")[1]


def merge_cookies(*cookie_dicts: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for d in cookie_dicts:
        merged.update(d)
    return merged


def apply_rb_cookies(result: dict[str, Any]) -> tuple[dict[str, str], str]:
    """Extract cookies and UA from an RB task result."""
    cookies = result.get("cookies_dict") or result.get("cookies") or {}
    if isinstance(cookies, list):
        cookies = {c["name"]: c["value"] for c in cookies if c.get("name")}
    ua = result.get("ua") or ""
    return cookies, ua
