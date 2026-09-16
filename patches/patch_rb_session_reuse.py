#!/usr/bin/env python3
"""RiskBypass: reuse warm Akamai session ~10x; align GC RB POST order with Five Below."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

GCO = Path("/opt/gco-checkers")
SHOP = Path("/opt/giftcard-shop")
RB_REUSE = "10"


def patch_gco_settings() -> None:
    for rel in ("gco_settings.json", "telegram_bot/checker_settings.json"):
        path = GCO / rel
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if str(data.get("rb_session_max_reuse")) == RB_REUSE:
            print(f"{rel} already rb_session_max_reuse={RB_REUSE}")
            continue
        data["rb_session_max_reuse"] = RB_REUSE
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"set {rel} rb_session_max_reuse={RB_REUSE}")


def patch_giftcardorder_rb() -> None:
    path = GCO / "giftcardorder_rb.py"
    text = path.read_text(encoding="utf-8")

    old_primary = """def primary_post_url_for_brand(brand: GiftcardBrand) -> str:
    \"\"\"HAR/probe-winning POST URL per brand.\"\"\"
    if brand.id == "goldencorral":
        return GCO_FH_POST
    if brand.id == "fivebelow":
        return GCO_FH_POST
    if brand.id in ("crackerbarrel", "firehousesubs"):
        return GCO_FH_POST
    return brand.bypass_post_url()"""
    new_primary = """def primary_post_url_for_brand(brand: GiftcardBrand) -> str:
    \"\"\"HAR/probe-winning POST URL per brand.\"\"\"
    if brand.id in ("fivebelow", "goldencorral", "stewleonards"):
        return brand.bypass_post_url()
    if brand.id in ("crackerbarrel", "firehousesubs"):
        return GCO_FH_POST
    return brand.bypass_post_url()"""
    if old_primary in text:
        text = text.replace(old_primary, new_primary, 1)
    elif "fivebelow\", \"goldencorral\", \"stewleonards\")" in text.split("primary_post_url_for_brand", 1)[-1][:400]:
        print("giftcardorder_rb primary_post_url already patched")
    else:
        raise SystemExit("primary_post_url_for_brand block not found")

    old_posts = """def post_urls_for_brand_rb(brand: GiftcardBrand) -> list[str]:
    \"\"\"POST URL fallbacks per brand (firehousesubs handler first — no reCAPTCHA).\"\"\"
    fh = GCO_FH_POST
    urls = [fh, brand.bypass_post_url(), brand.post_url(), f"{SITE}/mini_list.asp"]
    out: list[str] = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out"""
    new_posts = """def post_urls_for_brand_rb(brand: GiftcardBrand) -> list[str]:
    \"\"\"POST URL fallbacks per brand — Five Below / GC use crackerbarrel handler first.\"\"\"
    if brand.id in ("fivebelow", "goldencorral", "stewleonards"):
        urls = [
            brand.bypass_post_url(),
            GCO_FH_POST,
            brand.post_url(),
            f"{SITE}/mini_list.asp",
        ]
    else:
        urls = [GCO_FH_POST, brand.bypass_post_url(), brand.post_url(), f"{SITE}/mini_list.asp"]
    out: list[str] = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out"""
    if old_posts in text:
        text = text.replace(old_posts, new_posts, 1)
    elif "Five Below / GC use crackerbarrel handler first" in text:
        print("giftcardorder_rb post_urls already patched")
    else:
        raise SystemExit("post_urls_for_brand_rb block not found")

    path.write_text(text, encoding="utf-8")
    print("patched giftcardorder_rb.py")


def main() -> None:
    patch_gco_settings()
    patch_giftcardorder_rb()
    subprocess.run(
        [str(SHOP / "venv/bin/python"), "-c", "import card_recheck; print('import ok')"],
        check=True,
        cwd=SHOP,
    )
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")


if __name__ == "__main__":
    main()
