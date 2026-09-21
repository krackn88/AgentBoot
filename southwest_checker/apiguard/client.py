"""APIGuard client: fetch init and generate sensor headers."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from curl_cffi import requests

from southwest_checker.apiguard.generator import (
    DEFAULT_ROTATED_HEADER,
    EngineState,
    IOSDeviceProfile,
    RequestContext,
    generate_e_header,
    generate_g_header,
)
from southwest_checker.apiguard.headers import decode_e
from southwest_checker.apiguard.session import run_kernel_bootstrap
from southwest_checker.constants import API_KEY, BASE_URL, DEFAULT_HEADERS, HEADER_FAMILY, INIT_PATH, TOKEN_PATH


@dataclass
class InitSession:
    kernel_id: str
    sk: str
    ck: dict[str, Any] = field(default_factory=dict)
    header_a: str = ""
    header_b: str = "vl8bjr"
    header_c: str = ""
    header_d: str = ""
    header_z: str = "q"
    pid: str = ""


def _pid_from_capture(sensors: dict[str, str]) -> str:
    """Extract the previous kernel id chain from a captured -e header."""
    e_header = sensors.get(f"{HEADER_FAMILY}-e", "")
    if not e_header:
        return ""
    try:
        captured = json.loads(decode_e(e_header)["sensor"].decode("latin1"))
    except (KeyError, ValueError, json.JSONDecodeError):
        return ""
    return str(captured.get("pid") or "")


class APIGuardClient:
    """Generates fresh APIGuard sensor headers via /sw_check/ios/init."""

    def __init__(
        self,
        impersonate: str = "safari17_2_ios",
        proxy: str | None = None,
        template: InitSession | None = None,
        full_bootstrap: bool = False,
    ):
        self.impersonate = impersonate
        self.proxy = proxy
        self.session: InitSession | None = None
        self.template = template
        self.full_bootstrap = full_bootstrap
        self.profile = IOSDeviceProfile()
        self.engine = EngineState()
        self._session_obj = requests.Session(impersonate=impersonate)

    @classmethod
    def from_capture(cls, capture_data: dict[str, Any], **kwargs: Any) -> APIGuardClient:
        """Bootstrap from a Charles capture's sensor headers as template for -a/-c/-d."""
        sensors = capture_data.get("sensor_headers", {})
        template = InitSession(
            kernel_id=sensors.get(f"{HEADER_FAMILY}-f", ""),
            sk="",
            header_a=sensors.get(f"{HEADER_FAMILY}-a", ""),
            header_b=sensors.get(f"{HEADER_FAMILY}-b", "vl8bjr"),
            header_c=sensors.get(f"{HEADER_FAMILY}-c", ""),
            header_d=sensors.get(f"{HEADER_FAMILY}-d", ""),
            header_z=sensors.get(f"{HEADER_FAMILY}-z", "q"),
            pid=_pid_from_capture(sensors),
        )
        return cls(template=template, **kwargs)

    def _proxies(self) -> dict[str, str] | None:
        if not self.proxy:
            return None
        return {"http": self.proxy, "https": self.proxy}

    def _prev_kernel_id(self) -> str:
        if self.session:
            return self.session.kernel_id
        if self.template:
            return self.template.kernel_id
        return ""

    def _init_from_kernel(self) -> InitSession:
        """Execute init kernel JS and capture session headers via webkit bridge mock."""
        data = run_kernel_bootstrap(
            request_url=f"{BASE_URL}{TOKEN_PATH}",
            proxy=self.proxy,
        )
        headers = data.get("headers") or {}
        prev_pid = self._prev_kernel_id()

        self.session = InitSession(
            kernel_id=data.get("kernelId") or headers.get(f"{HEADER_FAMILY}-f", ""),
            sk=data.get("sk", ""),
            header_a=headers.get(f"{HEADER_FAMILY}-a", ""),
            header_b=headers.get(f"{HEADER_FAMILY}-b", "vl8bjr"),
            header_c=headers.get(f"{HEADER_FAMILY}-c", ""),
            header_d=headers.get(f"{HEADER_FAMILY}-d", ""),
            header_z=headers.get(f"{HEADER_FAMILY}-z", "q"),
            pid=prev_pid,
        )
        self.profile.kid = self.session.kernel_id
        self.profile.pid = prev_pid
        return self.session

    def _init_from_template(self) -> InitSession:
        """Use captured session headers as-is (no HTTP init / kernel rotation)."""
        if not self.template:
            raise RuntimeError("capture template required for template init")

        self.session = InitSession(
            kernel_id=self.template.kernel_id,
            sk=self.template.sk,
            ck=dict(self.template.ck),
            header_a=self.template.header_a,
            header_b=self.template.header_b or "vl8bjr",
            header_c=self.template.header_c,
            header_d=self.template.header_d,
            header_z=self.template.header_z or "q",
            pid=self.template.pid or "",
        )
        self.profile.kid = self.session.kernel_id
        self.profile.pid = self.template.pid or ""
        return self.session

    def init(self) -> InitSession:
        """Fetch fresh kernel from /sw_check/ios/init (or run JS kernel bootstrap)."""
        if self.full_bootstrap:
            return self._init_from_kernel()
        if self.template:
            return self._init_from_template()

        resp = self._session_obj.get(
            f"{BASE_URL}{INIT_PATH}",
            headers={
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "X-Channel-ID": "IOS",
                "X-API-Key": API_KEY,
            },
            timeout=30,
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        data = resp.json()

        kernel_id = data["kernelId"]
        sk = data.get("sk", "")
        ck = data.get("ck", {})
        prev_pid = self._prev_kernel_id()

        self.session = InitSession(
            kernel_id=kernel_id,
            sk=sk,
            ck=ck if isinstance(ck, dict) else {},
            header_a=self.template.header_a if self.template else "",
            header_b=self.template.header_b if self.template else "vl8bjr",
            header_c=self.template.header_c if self.template else "",
            header_d=self.template.header_d if self.template else "",
            header_z=self.template.header_z if self.template else "q",
            pid=prev_pid,
        )

        self.profile.kid = kernel_id
        self.profile.pid = prev_pid
        return self.session

    def generate_headers(
        self,
        uri: str = f"{BASE_URL}{TOKEN_PATH}",
        cookies: str | None = None,
    ) -> dict[str, str]:
        """Generate a full set of APIGuard headers for a protected request."""
        if not self.session:
            self.init()

        assert self.session is not None
        now_ms = int(time.time() * 1000)
        ctx = RequestContext(uri=uri, hdr=DEFAULT_ROTATED_HEADER, now_ms=now_ms)

        headers = dict(DEFAULT_HEADERS)
        headers["X-User-Experience-ID"] = str(uuid.uuid4()).upper()
        headers["x-swa-di-dtid"] = str(uuid.uuid4()).upper()

        headers[f"{HEADER_FAMILY}-e"] = generate_e_header(self.profile, self.engine, ctx)
        headers[f"{HEADER_FAMILY}-g"] = generate_g_header(self.profile, self.engine, now_ms)
        headers[f"{HEADER_FAMILY}-f"] = self.session.kernel_id
        headers[f"{HEADER_FAMILY}-b"] = self.session.header_b
        headers[f"{HEADER_FAMILY}-c"] = self.session.header_c
        headers[f"{HEADER_FAMILY}-d"] = self.session.header_d
        headers[f"{HEADER_FAMILY}-z"] = self.session.header_z

        if self.session.header_a:
            headers[f"{HEADER_FAMILY}-a"] = self.session.header_a

        if cookies:
            headers["Cookie"] = cookies

        return headers

    def refresh_if_needed(self, force: bool = False) -> None:
        if force or not self.session:
            self.init()
