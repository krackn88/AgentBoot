"""Online activation against the license server."""

from __future__ import annotations

import os
from typing import Any

import requests

from .hwid import get_hardware_id
from .license_core import validate_license_key
from .store import save_license

DEFAULT_API_URL = os.environ.get(
    "TROPIC_LICENSE_API_URL",
    "http://159.69.76.189:8081",
).rstrip("/")


def api_url() -> str:
    return os.environ.get("TROPIC_LICENSE_API_URL", DEFAULT_API_URL).rstrip("/")


def activate_online(activation_code: str, *, timeout: float = 20.0) -> str:
    """Exchange activation code for a signed license key."""
    hwid = get_hardware_id()
    resp = requests.post(
        f"{api_url()}/api/v1/activate",
        json={"activation_code": activation_code.strip(), "hardware_id": hwid},
        timeout=timeout,
    )
    data: dict[str, Any] = {}
    try:
        data = resp.json()
    except requests.JSONDecodeError:
        pass
    if not resp.ok:
        raise ValueError(data.get("error", resp.text[:200] or "Activation failed"))
    license_key = str(data.get("license_key", "")).strip()
    if not license_key:
        raise ValueError("Server did not return a license key")
    validate_license_key(license_key, hardware_id=hwid)
    save_license(license_key)
    return license_key


def validate_online(license_key: str, *, timeout: float = 10.0) -> bool:
    """Check license still valid on server (revocation/expiry)."""
    if not api_url():
        return True
    try:
        resp = requests.post(
            f"{api_url()}/api/v1/validate",
            json={"license_key": license_key.strip(), "hardware_id": get_hardware_id()},
            timeout=timeout,
        )
        if resp.status_code == 404:
            return True
        data = resp.json()
        return bool(resp.ok and data.get("valid"))
    except requests.RequestException:
        return True
