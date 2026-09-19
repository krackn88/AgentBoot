"""Signed license keys bound to a hardware id."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from ._secret import _LICENSE_SECRET
from .hwid import get_hardware_id

LICENSE_PREFIX = "TROPIC1"
LICENSE_VERSION = 1


@dataclass
class LicenseInfo:
    hardware_id: str
    customer: str
    issued_at: int
    expires_at: int | None
    raw_key: str

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return int(time.time()) > self.expires_at


def _secret() -> bytes:
    secret = _LICENSE_SECRET
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if secret.startswith(b"DEV-ONLY"):
        import os

        env = os.environ.get("TROPIC_LICENSE_SECRET", "").strip()
        if env:
            return env.encode("utf-8")
    return secret


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(_secret(), body, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _encode_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _b64url_encode(body)


def issue_license(
    hardware_id: str,
    customer: str,
    *,
    expires_at: int | None = None,
    issued_at: int | None = None,
) -> str:
    hwid = hardware_id.replace("-", "").upper()
    payload = {
        "v": LICENSE_VERSION,
        "hwid": hwid,
        "customer": customer.strip(),
        "issued_at": int(issued_at or time.time()),
        "expires_at": expires_at,
    }
    return f"{LICENSE_PREFIX}.{_encode_payload(payload)}.{_sign_payload(payload)}"


def parse_license_key(key: str) -> LicenseInfo:
    key = key.strip()
    parts = key.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_PREFIX:
        raise ValueError("Invalid license format")

    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    expected_sig = _sign_payload(payload)
    if not hmac.compare_digest(parts[2], expected_sig):
        raise ValueError("License signature mismatch")

    if int(payload.get("v", 0)) != LICENSE_VERSION:
        raise ValueError("Unsupported license version")

    return LicenseInfo(
        hardware_id=str(payload["hwid"]).upper(),
        customer=str(payload.get("customer", "")),
        issued_at=int(payload.get("issued_at", 0)),
        expires_at=payload.get("expires_at"),
        raw_key=key,
    )


def validate_license_key(key: str, *, hardware_id: str | None = None) -> LicenseInfo:
    info = parse_license_key(key)
    current = (hardware_id or get_hardware_id()).replace("-", "").upper()
    if info.hardware_id != current:
        raise ValueError("License is not valid for this computer")
    if info.is_expired:
        raise ValueError("License has expired")
    return info
