"""Persist combos, proxies, hits, and app settings."""

from __future__ import annotations

import json
import time
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


def combo_key(email: str, password: str) -> str:
    return f"{email}:{password}"


class ProgressTracker:
    """Track checked combos so runs can resume after stop or reload."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.checked_path = self.data_dir / "checked.txt"
        self.progress_path = self.data_dir / "progress.json"
        self._checked: set[str] | None = None

    def _ensure_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_checked_set(self) -> set[str]:
        if self._checked is not None:
            return self._checked
        checked: set[str] = set()
        if self.checked_path.exists():
            for line in load_lines(self.checked_path):
                key = line.strip()
                if key:
                    checked.add(key)
        self._checked = checked
        return checked

    def load_progress(self) -> dict[str, Any]:
        if not self.progress_path.exists():
            return {}
        try:
            data = json.loads(self.progress_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save_progress(self, progress: dict[str, Any]) -> None:
        self._ensure_dir()
        progress["updated_at"] = time.time()
        self.progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")

    def checked_count(self) -> int:
        progress = self.load_progress()
        stored = int(progress.get("checked_count", 0) or 0)
        file_count = len(self._load_checked_set())
        return max(stored, file_count)

    def hits_count(self) -> int:
        return int(self.load_progress().get("hits_count", 0) or 0)

    def fails_count(self) -> int:
        return int(self.load_progress().get("fails_count", 0) or 0)

    def mark_checked(self, email: str, password: str, *, success: bool) -> None:
        key = combo_key(email, password)
        checked = self._load_checked_set()
        if key in checked:
            return

        checked.add(key)
        self._ensure_dir()
        with self.checked_path.open("a", encoding="utf-8") as fh:
            fh.write(key + "\n")

        progress = self.load_progress()
        progress["checked_count"] = int(progress.get("checked_count", 0) or 0) + 1
        if success:
            progress["hits_count"] = int(progress.get("hits_count", 0) or 0) + 1
        else:
            progress["fails_count"] = int(progress.get("fails_count", 0) or 0) + 1
        self.save_progress(progress)

    def mark_checked_many(self, combos: list[tuple[str, str]]) -> int:
        checked = self._load_checked_set()
        new_lines: list[str] = []
        for email, password in combos:
            key = combo_key(email, password)
            if key in checked:
                continue
            checked.add(key)
            new_lines.append(key)
        if not new_lines:
            return 0

        self._ensure_dir()
        with self.checked_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(new_lines) + "\n")

        progress = self.load_progress()
        progress["checked_count"] = int(progress.get("checked_count", 0) or 0) + len(new_lines)
        self.save_progress(progress)
        return len(new_lines)

    def set_remaining_count(self, remaining: int) -> None:
        progress = self.load_progress()
        progress["remaining_count"] = remaining
        self.save_progress(progress)

    def filter_unchecked(self, combos: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
        checked = self._load_checked_set()
        if not checked:
            return combos, 0
        out: list[tuple[str, str]] = []
        skipped = 0
        for email, password in combos:
            if combo_key(email, password) in checked:
                skipped += 1
            else:
                out.append((email, password))
        return out, skipped

    def merge_reload(
        self,
        parsed: list[tuple[str, str]],
        current_remaining: list[tuple[str, str]],
    ) -> tuple[list[tuple[str, str]], int, str]:
        """Resume when the same full combo list is pasted again."""
        if not parsed:
            return [], 0, ""

        old_set = set(current_remaining)
        parsed_set = set(parsed)
        if old_set and old_set.issubset(parsed_set) and len(parsed_set) > len(old_set):
            inferred = [combo for combo in parsed if combo not in old_set]
            added = self.mark_checked_many(inferred)
            remaining = [combo for combo in parsed if combo in old_set]
            return remaining, added, f"Resumed same list — skipped {added} already checked"

        filtered, skipped = self.filter_unchecked(parsed)
        if skipped:
            return filtered, skipped, f"Skipped {skipped} already checked combos"
        return parsed, 0, ""
