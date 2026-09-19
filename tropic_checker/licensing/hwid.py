"""Stable hardware fingerprint for license binding."""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
import uuid


def _run_wmic(args: list[str]) -> str:
    if platform.system() != "Windows":
        return ""
    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        out = subprocess.check_output(
            ["wmic", *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
            creationflags=creationflags,
        )
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[1]
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _windows_machine_guid() -> str:
    if platform.system() != "Windows":
        return ""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except OSError:
        return ""


def _collect_parts() -> list[str]:
    parts: list[str] = []
    guid = _windows_machine_guid()
    if guid:
        parts.append(f"guid:{guid}")

    board = _run_wmic(["baseboard", "get", "serialnumber"])
    if board and board.lower() not in {"to be filled by o.e.m.", "default string", "none"}:
        parts.append(f"board:{board}")

    product_uuid = _run_wmic(["csproduct", "get", "uuid"])
    if product_uuid:
        parts.append(f"product:{product_uuid}")

    if not parts:
        parts.append(f"node:{uuid.getnode():012x}")
    return parts


def get_hardware_id() -> str:
    """Return a stable uppercase hex id for this machine."""
    blob = "|".join(_collect_parts()).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:32].upper()


def format_hwid(raw: str) -> str:
    raw = raw.replace("-", "").upper()
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))
