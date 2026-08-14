"""RiskByPass API client for akamai, perimeterx, recaptcha, and tls_forward tasks."""

from __future__ import annotations

import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://riskbypass.com"
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_TIMEOUT = 120


class RiskByPassError(Exception):
    """Raised when an RB task fails or times out."""


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
        page_fp: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_type": "akamai",
            "proxy": proxy,
            "target_url": target_url,
            "akamai_js_url": akamai_js_url,
        }
        if init_cookies:
            payload["init_cookies"] = init_cookies
        if page_fp:
            payload["page_fp"] = page_fp
        return self.run_task(payload)

    def perimeterx_invisible(
        self,
        *,
        proxy: str,
        target_url: str,
        px_app_id: str | None = None,
        init_cookies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_type": "perimeterx_invisible",
            "proxy": proxy,
            "target_url": target_url,
        }
        if px_app_id:
            payload["pxAppId"] = px_app_id
        if init_cookies:
            payload["init_cookies"] = init_cookies
        return self.run_task(payload)

    def perimeterx_hold(
        self,
        *,
        proxy: str,
        target_url: str,
        px_app_id: str | None = None,
        init_cookies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_type": "perimeterx_hold",
            "proxy": proxy,
            "target_url": target_url,
        }
        if px_app_id:
            payload["pxAppId"] = px_app_id
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
        target_url: str,
        method: str,
        headers: dict[str, str],
        cookies: dict[str, str],
        ua: str,
        body: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_type": "tls_forward",
            "proxy": proxy,
            "target_url": target_url,
            "target_method": method.upper(),
            "target_headers": headers,
            "cookies": cookies,
            "ua": ua,
        }
        if body is not None:
            payload["target_body"] = body
        return self.run_task(payload)


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
