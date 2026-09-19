"""Customer download catalog for the public portal."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = Path(
    os.environ.get(
        "CUSTOMER_DOWNLOADS_DIR",
        os.environ.get("TROPIC_CUSTOMER_DOWNLOADS_DIR", APP_ROOT / "downloads" / "customer"),
    )
)

CATALOG = [
    {
        "filename": "TropicChecker-Customer-windows-x64.zip",
        "title": "Windows (64-bit)",
        "description": "Licensed customer edition. Extract and run TropicChecker.exe — no Python required.",
        "platform": "windows",
    },
    {
        "filename": "TropicChecker-Customer.exe",
        "title": "Windows EXE (single file)",
        "description": "Same app as a single portable executable.",
        "platform": "windows",
    },
]


def _fmt_size(num: int) -> str:
    if num >= 1024 * 1024:
        return f"{num / (1024 * 1024):.1f} MB"
    if num >= 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num} B"


def list_downloads() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in CATALOG:
        path = DOWNLOADS_DIR / entry["filename"]
        if not path.is_file():
            continue
        stat = path.stat()
        items.append({
            "name": entry["filename"],
            "title": entry["title"],
            "description": entry["description"],
            "platform": entry["platform"],
            "url": f"/portal/files/{entry['filename']}",
            "size": _fmt_size(stat.st_size),
            "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M UTC"),
        })
    return items


def resolve_file(filename: str) -> Path | None:
    safe = Path(filename).name
    path = DOWNLOADS_DIR / safe
    if path.is_file():
        return path
    return None
