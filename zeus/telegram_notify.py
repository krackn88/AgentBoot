"""Telegram notifications for active Zeus subscription hits."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import httpx

from .checker import CheckResult

_DATA_DIR = Path(os.environ.get("ZEUS_DATA_DIR", "data"))
_CHAT_ID_FILE = _DATA_DIR / "telegram_chat_id"
_OFFSET_FILE = _DATA_DIR / "telegram_updates_offset"
_DISCOVERED_FILE = _DATA_DIR / "telegram_discovered_chats.json"


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    env_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if env_id:
        return env_id
    try:
        return _CHAT_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_configured() -> bool:
    return bool(_bot_token() and _chat_id())


def save_chat_id(chat_id: str) -> None:
    chat_id = str(chat_id).strip()
    if not chat_id:
        return
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CHAT_ID_FILE.write_text(chat_id, encoding="utf-8")
    os.environ["TELEGRAM_CHAT_ID"] = chat_id


def should_notify(result: CheckResult) -> bool:
    return result.status == "HIT" and bool(result.active)


def format_hit_message(result: CheckResult) -> str:
    lines = [
        "Zeus Network HIT",
        "",
        result.format_line(),
    ]
    if result.purchases:
        lines.append("")
        lines.append(f"Purchases: {', '.join(result.purchases)}")
    return "\n".join(lines)


def send_message(text: str) -> tuple[bool, str]:
    token = _bot_token()
    chat_id = _chat_id()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN not set"
    if not chat_id:
        return False, "TELEGRAM_CHAT_ID not set"

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
        data = response.json()
        if response.is_success and data.get("ok"):
            return True, "sent"
        return False, data.get("description", response.text[:200])
    except httpx.HTTPError as exc:
        return False, str(exc)


def _load_discovered() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_DISCOVERED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_discovered(chats: dict[str, dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DISCOVERED_FILE.write_text(json.dumps(chats), encoding="utf-8")


def _load_offset() -> int:
    try:
        return int(_OFFSET_FILE.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def _save_offset(offset: int) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def poll_updates() -> list[dict[str, Any]]:
    token = _bot_token()
    if not token:
        return list(_load_discovered().values())

    chats = _load_discovered()
    offset = _load_offset()
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 0},
            )
        data = response.json()
        if not data.get("ok"):
            return list(chats.values())
        for item in data.get("result", []):
            update_id = int(item.get("update_id", 0))
            if update_id >= offset:
                offset = update_id + 1
            msg = item.get("message") or item.get("edited_message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            key = str(chat_id)
            chats[key] = {
                "chat_id": key,
                "type": chat.get("type"),
                "username": chat.get("username"),
                "first_name": chat.get("first_name"),
            }
        if offset:
            _save_offset(offset)
        _save_discovered(chats)
    except httpx.HTTPError:
        pass
    return list(chats.values())


def register_chat(preferred_chat_id: str | None = None) -> tuple[bool, str]:
    chats = poll_updates()
    if not chats:
        return False, "No pending chats — message your bot on Telegram first"
    if preferred_chat_id:
        for chat in chats:
            if str(chat.get("chat_id")) == str(preferred_chat_id):
                save_chat_id(str(preferred_chat_id))
                return True, str(preferred_chat_id)
    for chat in chats:
        if chat.get("type") == "private":
            save_chat_id(str(chat["chat_id"]))
            return True, str(chat["chat_id"])
    chat_id = str(chats[0]["chat_id"])
    save_chat_id(chat_id)
    return True, chat_id


def notify_hit(result: CheckResult) -> None:
    if not should_notify(result) or not is_configured():
        return

    text = format_hit_message(result)

    def _send() -> None:
        send_message(text)

    threading.Thread(target=_send, daemon=True).start()
