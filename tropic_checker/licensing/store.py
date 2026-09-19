"""Persist activated license on the customer machine."""

from __future__ import annotations

import os
from pathlib import Path


def license_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or Path.home()
        return Path(base) / "TropicChecker"
    return Path.home() / ".tropic-checker"


def license_path() -> Path:
    return license_dir() / "license.key"


def load_saved_license() -> str:
    path = license_path()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def save_license(key: str) -> None:
    path = license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.strip() + "\n", encoding="utf-8")
