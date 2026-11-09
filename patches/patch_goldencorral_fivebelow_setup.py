#!/usr/bin/env python3
"""Align Golden Corral checker with Five Below (POST URLs, referers, proxy rotation)."""

from __future__ import annotations

import subprocess
from pathlib import Path

GCO = Path("/opt/gco-checkers")
SHOP = Path("/opt/giftcard-shop")


def patch_giftcardorder_brands() -> None:
    path = GCO / "giftcardorder_brands.py"
    text = path.read_text(encoding="utf-8")
    old = """        if self.host == "fivebelow":
            return "https://www.giftcardorder.net/crackerbarrel/mini_list.asp"
        if self.host == "crackerbarrel":
            return "https://www.giftcardorder.net/firehousesubs/mini_list.asp"
        if self.host in ("goldencorral", "stewleonards"):
            return "https://www.giftcardorder.net/firehousesubs/mini_list.asp"
"""
    new = """        if self.host in ("fivebelow", "goldencorral", "stewleonards"):
            return "https://www.giftcardorder.net/crackerbarrel/mini_list.asp"
        if self.host == "crackerbarrel":
            return "https://www.giftcardorder.net/firehousesubs/mini_list.asp"
"""
    if old not in text:
        if "fivebelow\", \"goldencorral\", \"stewleonards\")" in text:
            print("giftcardorder_brands already patched")
            return
        raise SystemExit("giftcardorder_brands bypass_post_url block not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("patched giftcardorder_brands.py")


def patch_firehouse_checker() -> None:
    path = GCO / "firehouse_checker.py"
    text = path.read_text(encoding="utf-8")

    old_refs = """    if brand_id in ("goldencorral", "stewleonards"):
        return GC_DIRECT_POST_REFERERS
    if brand_id in ("fivebelow", "firehousesubs"):
        return FB_DIRECT_POST_REFERERS"""
    new_refs = """    if brand_id in ("fivebelow", "firehousesubs", "goldencorral", "stewleonards"):
        return FB_DIRECT_POST_REFERERS"""
    if old_refs in text:
        text = text.replace(old_refs, new_refs, 1)

    old_imp = '"goldencorral": ("firefox135", "chrome120", "safari184", "safari18_0", "edge101", "chrome124"),'
    new_imp = '"goldencorral": ("chrome131", "firefox135", "safari18_0", "edge101", "chrome120", "safari17_0", "chrome124"),'
    if old_imp in text:
        text = text.replace(old_imp, new_imp, 1)

    old_posts = """    if brand.id in ("goldencorral", "stewleonards"):
        return [
            GCO_FH_POST,
            brand.post_url(),
            brand.bypass_post_url(),
            "https://www.giftcardorder.net/mini_list.asp",
        ]
    if brand.id == "firehousesubs":"""
    new_posts = """    if brand.id in ("goldencorral", "stewleonards"):
        return [
            GCO_FH_POST,
            brand.bypass_post_url(),
            brand.post_url(),
            "https://www.giftcardorder.net/mini_list.asp",
        ]
    if brand.id == "firehousesubs":"""
    if old_posts in text:
        text = text.replace(old_posts, new_posts, 1)

    path.write_text(text, encoding="utf-8")
    print("patched firehouse_checker.py")


def patch_gco_recheck_cli() -> None:
    path = SHOP / "recheck_runners" / "gco_recheck_cli.py"
    new_content = '''#!/usr/bin/env python3
"""Live GCO balance recheck — run with gco-checkers venv from /opt/gco-checkers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _resolve_root() -> Path:
    explicit = os.environ.get("GCO_ROOT", "").strip()
    if explicit:
        return Path(explicit).resolve()
    return Path("/opt/gco-checkers").resolve()


def _load_proxies(proxies_file: Path) -> list[str]:
    if not proxies_file.exists():
        return []
    out: list[str] = []
    for line in proxies_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _is_definitive(result: dict[str, Any]) -> bool:
    return result.get("kind") in ("hit", "fail")


def _should_keep_trying(result: dict[str, Any]) -> bool:
    if _is_definitive(result):
        return False
    err = str(result.get("error") or result.get("fail_key") or result.get("reason") or "").lower()
    if result.get("retryable"):
        return True
    if any(token in err for token in ("no proxies", "missing pin", "invalid_pin", "bad_card")):
        return False
    transient = (
        "403",
        "429",
        "akamai",
        "cloudflare",
        "rate limit",
        "timeout",
        "proxy",
        "service_unavailable",
        "rb_",
        "balance_unparsed",
        "blocked",
        "json",
        "exception",
        "light_page",
    )
    return any(token in err for token in transient)


def main() -> int:
    parser = argparse.ArgumentParser(description="GCO live recheck for giftcard shop")
    parser.add_argument("brand_id")
    parser.add_argument("card")
    parser.add_argument("pin", nargs="?", default="")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    root = _resolve_root()
    bot_dir = root / "telegram_bot"
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(bot_dir.parent))

    from telegram_bot import checker as tg_checker

    tg_checker.configure(cbolo_root=root)
    tg_checker.init_settings(cbolo_root=root)

    proxies_file = root / "proxies.txt"
    proxies = _load_proxies(proxies_file)
    proxy_count = max(1, len(proxies))
    rounds = max(1, int(args.retries))
    max_tries = max(rounds * proxy_count, rounds, proxy_count * 3)

    result: dict[str, Any] = {"kind": "error", "error": "no attempt", "retryable": True}
    for attempt in range(1, max_tries + 1):
        result = tg_checker.recheck_card(
            args.card,
            args.pin,
            brand_id=args.brand_id,
            retries=1,
            fast=True,
        )
        if isinstance(result, dict):
            result.pop("balance_image", None)
        if _is_definitive(result):
            break
        if not _should_keep_trying(result):
            break
        if attempt < max_tries:
            time.sleep(0.5 if attempt < max_tries else 0)

    if result.get("kind") == "error" and _should_keep_trying(result):
        result["retryable"] = True

    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
    path.write_text(new_content, encoding="utf-8")
    print("patched gco_recheck_cli.py")


def main() -> None:
    patch_giftcardorder_brands()
    patch_firehouse_checker()
    patch_gco_recheck_cli()
    subprocess.run(
        [
            str(SHOP / "venv/bin/python"),
            "-c",
            "import card_recheck; print('import ok')",
        ],
        check=True,
        cwd=SHOP,
    )
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")


if __name__ == "__main__":
    main()
