"""Persist combos, proxies, hits, and app settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .api import AccountResult, parse_combo_line

APP_DIR = Path.home() / ".tropic-checker"
DATA_DIR = APP_DIR / "data"
CONFIG_PATH = APP_DIR / "config.json"
HITS_PATH = DATA_DIR / "hits.txt"
COMBOS_PATH = DATA_DIR / "combos.txt"
PROXIES_PATH = DATA_DIR / "proxies.txt"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return default_config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = default_config()
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return default_config()


def save_config(config: dict[str, Any]) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def default_config() -> dict[str, Any]:
    return {
        "combo_path": str(COMBOS_PATH),
        "proxy_path": str(PROXIES_PATH),
        "hits_path": str(HITS_PATH),
        "threads": 5,
        "window_geometry": "1200x780",
    }


def load_lines(path: str | Path) -> list[str]:
    path = Path(path)
    if not path.exists():
        return []
    return [line.rstrip("\n") for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]


def save_lines(path: str | Path, lines: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def load_combos(path: str | Path | None = None) -> list[tuple[str, str]]:
    path = Path(path or COMBOS_PATH)
    combos: list[tuple[str, str]] = []
    for line in load_lines(path):
        parsed = parse_combo_line(line)
        if parsed:
            combos.append(parsed)
    return combos


def save_combos(path: str | Path, combos: list[tuple[str, str]]) -> None:
    save_lines(path, [f"{email}:{password}" for email, password in combos])


def load_proxies(path: str | Path | None = None) -> list[str]:
    path = Path(path or PROXIES_PATH)
    proxies: list[str] = []
    for line in load_lines(path):
        line = line.strip()
        if line and not line.startswith("#"):
            proxies.append(line)
    return proxies


def save_proxies(path: str | Path, proxies: list[str]) -> None:
    save_lines(path, proxies)


def load_hits(path: str | Path | None = None) -> list[str]:
    path = Path(path or HITS_PATH)
    hits: list[str] = []
    for line in load_lines(path):
        line = line.strip()
        if line and not line.startswith("#"):
            hits.append(line)
    return hits


def save_hits(path: str | Path, hits: list[str]) -> None:
    save_lines(path, hits)


def append_hit(path: str | Path, result: AccountResult) -> None:
    path = Path(path)
    ensure_dirs()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(result.summary_line() + "\n")


def hit_line_from_result(result: AccountResult) -> str:
    return result.summary_line()
