#!/usr/bin/env python3
"""Live cbolo balance recheck — run with cbolo-checker venv from /opt/cbolo-checker."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _resolve_root() -> Path:
    explicit = os.environ.get("CBOLO_ROOT", "").strip()
    if explicit:
        return Path(explicit).resolve()
    return Path("/opt/cbolo-checker").resolve()


def _load_proxies(proxies_file: Path) -> list[str]:
    if not proxies_file.exists():
        return []
    out: list[str] = []
    for line in proxies_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _next_proxy(proxies: list[str], idx: int) -> tuple[str, int]:
    if not proxies:
        return "", idx
    return proxies[idx % len(proxies)], idx + 1


def _resolve_proxies_file(root: Path, profile_id: str) -> Path:
    specific = root / f"proxies_{profile_id.strip()}.txt"
    if specific.is_file():
        return specific
    return root / "proxies.txt"


def _resolve_settings_file(root: Path, profile_id: str) -> Path:
    specific = root / f"cbolo_settings_{profile_id.strip()}.json"
    if specific.is_file():
        return specific
    return root / "cbolo_settings.json"


def _is_definitive(result: dict[str, Any]) -> bool:
    return result.get("kind") in ("hit", "fail")


def _should_keep_trying(result: dict[str, Any]) -> bool:
    """Keep rotating proxies until we get a hit or a definitive dead-card fail."""
    if _is_definitive(result):
        return False
    err = str(result.get("error") or result.get("fail_key") or "").lower()
    if result.get("retryable"):
        return True
    non_retryable = (
        "no proxies",
        "unknown profile",
        "missing runner",
        "missing python",
    )
    if any(token in err for token in non_retryable):
        return False
    transient_tokens = (
        "1015",
        "cloudflare",
        "rate limit",
        "rate-limited",
        "timeout",
        "proxy",
        "craft_balance_bad_json",
        "craft_balance:",
        "blocked",
        "403",
        "429",
        "service_unavailable",
        "too_many_attempts",
        "json",
        "exception",
    )
    return any(token in err for token in transient_tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cbolo live recheck for giftcard shop")
    parser.add_argument("profile_id")
    parser.add_argument("card")
    parser.add_argument("pin", nargs="?", default="")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    root = _resolve_root()
    sys.path.insert(0, str(root))

    import cbolo_checker as cc
    from cbolo_checker import check_one, profile_override

    cc.ROOT = root
    cc.PROFILES_FILE = root / "olo_profiles.json"
    cc.PROXIES_FILE = _resolve_proxies_file(root, args.profile_id)
    cc.SETTINGS_FILE = _resolve_settings_file(root, args.profile_id)

    try:
        proxies = cc.load_proxies(cc.PROXIES_FILE)
    except ValueError:
        print(json.dumps({"kind": "error", "error": "no proxies", "retryable": False}))
        return 1

    result: dict[str, Any] = {"kind": "error", "error": "no attempt", "retryable": True}
    proxy_idx = 0
    rounds = max(1, int(args.retries))
    proxy_count = max(1, len(proxies))
    max_tries = max(rounds * proxy_count, rounds, proxy_count * 3)

    with profile_override(args.profile_id):
        brand = cc.brand_config()
        check_pin = "" if brand.get("pinless") else (args.pin or "")
        for attempt in range(1, max_tries + 1):
            proxy_base, proxy_idx = _next_proxy(proxies, proxy_idx)
            try:
                result = check_one(
                    args.card,
                    check_pin,
                    proxy_base=proxy_base,
                    log=lambda *_a, **_k: None,
                )
            except Exception as exc:
                result = {
                    "kind": "error",
                    "fail_key": "exception",
                    "error": str(exc),
                    "retryable": True,
                }
            if _is_definitive(result):
                break
            if not _should_keep_trying(result):
                break
            if attempt < max_tries:
                time.sleep(0.5)
        else:
            if not _is_definitive(result):
                result = {
                    **result,
                    "kind": "error",
                    "retryable": True,
                    "error": str(result.get("error") or "recheck exhausted proxies"),
                }

    if result.get("kind") == "error" and _should_keep_trying(result):
        result["retryable"] = True

    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
