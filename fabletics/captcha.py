from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .config import BASE_URL, RECAPTCHA_ACTION, RECAPTCHA_SITE_KEY

CAPSOLVER_CREATE_URL = "https://api.capsolver.com/createTask"
CAPSOLVER_RESULT_URL = "https://api.capsolver.com/getTaskResult"


def captcha_api_key() -> str | None:
    key = os.environ.get("CAPSOLVER_API_KEY", "").strip()
    return key or None


def needs_captcha(message: str) -> bool:
    lower = message.lower()
    return "recaptcha" in lower or (
        "captcha" in lower and "authentication" not in lower
    )


def _capsolver_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CapSolver HTTP {exc.code}: {body[:200]}") from exc


def _poll_capsolver_task(api_key: str, task_id: str, timeout: int = 120) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _capsolver_post(
            CAPSOLVER_RESULT_URL,
            {"clientKey": api_key, "taskId": task_id},
        )
        status = result.get("status")
        if status == "ready":
            token = (result.get("solution") or {}).get("gRecaptchaResponse")
            if token:
                return token
            raise RuntimeError("CapSolver returned no gRecaptchaResponse")
        if status == "failed" or result.get("errorId"):
            raise RuntimeError(result.get("errorDescription") or "CapSolver task failed")
        time.sleep(2)
    raise RuntimeError("CapSolver timed out")


def _create_task(api_key: str, task: dict) -> str:
    result = _capsolver_post(
        CAPSOLVER_CREATE_URL,
        {"clientKey": api_key, "task": task},
    )
    if result.get("errorId"):
        raise RuntimeError(result.get("errorDescription") or "CapSolver createTask failed")
    task_id = result.get("taskId")
    if not task_id:
        raise RuntimeError("CapSolver did not return taskId")
    return task_id


def _recaptcha_site_key() -> str:
    return os.environ.get("RECAPTCHA_SITE_KEY", RECAPTCHA_SITE_KEY).strip()


def _recaptcha_page_url() -> str:
    return os.environ.get("RECAPTCHA_PAGE_URL", f"{BASE_URL}/").strip()


def _recaptcha_action() -> str:
    return os.environ.get("RECAPTCHA_ACTION", RECAPTCHA_ACTION).strip()


def _solver_proxy() -> str | None:
    raw = os.environ.get("CAPSOLVER_PROXY", os.environ.get("FABLETICS_PROXY", "")).strip()
    return raw or None


def solve_recaptcha(timeout: int = 120) -> str | None:
    api_key = captcha_api_key()
    if not api_key:
        return None

    page_url = _recaptcha_page_url()
    site_key = _recaptcha_site_key()
    action = _recaptcha_action()
    proxy = _solver_proxy()

    attempts: list[dict] = []
    if proxy:
        attempts.extend(
            [
                {
                    "type": "ReCaptchaV2Task",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "proxy": proxy,
                },
                {
                    "type": "ReCaptchaV3Task",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "pageAction": action,
                    "proxy": proxy,
                },
            ]
        )
    attempts.extend(
        [
            {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            },
            {
                "type": "ReCaptchaV3TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
                "pageAction": action,
            },
        ]
    )

    last_error: Exception | None = None
    for task in attempts:
        try:
            task_id = _create_task(api_key, task)
            return _poll_capsolver_task(api_key, task_id, timeout=timeout)
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return None
