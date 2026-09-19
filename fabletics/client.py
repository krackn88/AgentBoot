from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import Session

from .config import (
    API_KEY,
    APP_JS_VERSION,
    APP_NATIVE_VERSION,
    APP_PLATFORM,
    BASE_URL,
    DEFAULT_TIMEOUT,
    STORE_DOMAIN,
    TLS_IMPERSONATE,
    USER_AGENT,
)


class FableticsAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
        captcha_required: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.captcha_required = captcha_required


@dataclass
class LoginResult:
    access_token: str
    customer: dict[str, Any]


class FableticsClient:
    def __init__(self, proxy: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._session = Session(impersonate=TLS_IMPERSONATE)
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def _base_headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "x-api-key": API_KEY,
            "x-tfg-storedomain": STORE_DOMAIN,
            "x-app-platform": APP_PLATFORM,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "x-app-native-version": APP_NATIVE_VERSION,
            "x-app-js-version": APP_JS_VERSION,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{BASE_URL}{path}"
        response = self._session.request(
            method,
            url,
            headers=self._base_headers(token),
            params=params,
            json=json,
            timeout=self.timeout,
        )

        if response.status_code >= 500:
            raise FableticsAPIError(
                f"Server error on {path}: {response.status_code}",
                status_code=response.status_code,
                retryable=True,
            )
        if response.status_code == 429:
            raise FableticsAPIError(
                "Rate limited",
                status_code=response.status_code,
                retryable=True,
            )

        try:
            body = response.json()
        except Exception:
            body = response.text

        if response.status_code >= 400:
            message = body.get("message") if isinstance(body, dict) else str(body)
            raise FableticsAPIError(
                message or f"Request failed: {response.status_code}",
                status_code=response.status_code,
            )

        return body

    def create_guest_session(self) -> str:
        response = self._session.get(
            f"{BASE_URL}/api/sessions",
            headers=self._base_headers(),
            timeout=self.timeout,
        )

        if response.status_code >= 500:
            raise FableticsAPIError(
                f"Failed to create guest session: {response.status_code}",
                status_code=response.status_code,
                retryable=True,
            )
        if response.status_code >= 400:
            raise FableticsAPIError(
                f"Failed to create guest session: {response.status_code}",
                status_code=response.status_code,
            )

        auth_header = response.headers.get("authorization") or response.headers.get("Authorization")
        if not auth_header:
            raise FableticsAPIError("Guest session response missing authorization header")

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            raise FableticsAPIError("Guest session returned an empty token")
        return token

    def login(self, username: str, password: str) -> LoginResult:
        guest_token = self.create_guest_session()
        response = self._session.post(
            f"{BASE_URL}/api/auth/login",
            headers=self._base_headers(guest_token),
            json={"username": username, "password": password},
            timeout=self.timeout,
        )

        if response.status_code in (429, 500, 502, 503, 504):
            raise FableticsAPIError(
                f"Login failed with status {response.status_code}",
                status_code=response.status_code,
                retryable=True,
            )

        try:
            body = response.json()
        except Exception:
            raise FableticsAPIError(f"Invalid login response: {response.text[:200]}")

        if not (200 <= response.status_code < 300):
            message = body.get("message", "Login failed") if isinstance(body, dict) else "Login failed"
            lower = str(message).lower()
            captcha_required = "recaptcha" in lower
            raise FableticsAPIError(
                message,
                status_code=response.status_code,
                captcha_required=captcha_required,
            )

        access_token = body.get("accessToken")
        customer = body.get("customer") or {}
        if not access_token:
            raise FableticsAPIError("Login succeeded but no access token was returned")

        return LoginResult(access_token=access_token, customer=customer)

    def get(self, path: str, token: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, token, params=params)
