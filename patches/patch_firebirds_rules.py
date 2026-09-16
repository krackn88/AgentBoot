#!/usr/bin/env python3
"""Firebirds: minimum $25 tier, one card per order."""

from __future__ import annotations

import subprocess
from pathlib import Path

SHOP = Path("/opt/giftcard-shop")


def patch_catalog_tiers() -> None:
    path = SHOP / "catalog_tiers.py"
    text = path.read_text(encoding="utf-8")
    if "BRAND_MIN_TIER" in text:
        print("catalog_tiers already has BRAND_MIN_TIER")
        return

    anchor = "STANDARD_TIERS = [10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250]\n"
    insert = anchor + """
BRAND_MIN_TIER: dict[str, float] = {
    "Firebirds": 25.0,
}

BRAND_MAX_ORDER_QUANTITY: dict[str, int] = {
    "Firebirds": 1,
}


def min_tier_for_brand(brand: str) -> float:
    return float(BRAND_MIN_TIER.get(brand, 5.0))


def max_quantity_for_brand(brand: str) -> int:
    from config import MAX_ORDER_QUANTITY

    return int(BRAND_MAX_ORDER_QUANTITY.get(brand, MAX_ORDER_QUANTITY))


"""
    if anchor not in text:
        raise SystemExit("STANDARD_TIERS anchor not found")
    text = text.replace(anchor, insert, 1)

    old_build = """def build_tiers_from_rows(rows: list[dict[str, Any]], *, brand: str = "") -> list[dict[str, Any]]:
    candidate_tiers = {5.0, *STANDARD_TIERS}"""
    new_build = """def build_tiers_from_rows(rows: list[dict[str, Any]], *, brand: str = "") -> list[dict[str, Any]]:
    brand_min = min_tier_for_brand(brand) if brand else 5.0
    candidate_tiers = {t for t in {5.0, *STANDARD_TIERS} if t >= brand_min}"""
    if old_build not in text:
        raise SystemExit("build_tiers_from_rows candidate_tiers block not found")
    text = text.replace(old_build, new_build, 1)

    path.write_text(text, encoding="utf-8")
    print("patched catalog_tiers.py")


def patch_db() -> None:
    path = SHOP / "db.py"
    text = path.read_text(encoding="utf-8")

    old_import = (
        "from catalog_tiers import brand_meta, build_tiers_from_rows, nearest_tier, "
        "order_meets_minimum, min_quantity_for_tier, storefront_copy"
    )
    new_import = (
        "from catalog_tiers import brand_meta, build_tiers_from_rows, max_quantity_for_brand, "
        "min_tier_for_brand, nearest_tier, order_meets_minimum, min_quantity_for_tier, storefront_copy"
    )
    if "max_quantity_for_brand" not in text:
        if old_import not in text:
            raise SystemExit("db.py catalog_tiers import not found")
        text = text.replace(old_import, new_import, 1)

    old_brands = """                "tier_count": len(tiers),
                **storefront_copy(row["brand"]),
            }
        )"""
    new_brands = """                "tier_count": len(tiers),
                "max_order_quantity": max_quantity_for_brand(row["brand"]),
                "min_tier": min_tier_for_brand(row["brand"]),
                **storefront_copy(row["brand"]),
            }
        )"""
    if '"max_order_quantity"' not in text:
        if old_brands not in text:
            raise SystemExit("list_brands append block not found")
        text = text.replace(old_brands, new_brands, 1)

    old_reserve_check = """    if not order_meets_minimum(target_tier, quantity):
        return None
    with _connect() as conn:"""
    new_reserve_check = """    if not order_meets_minimum(target_tier, quantity):
        return None
    if target_tier < min_tier_for_brand(brand):
        return None
    if quantity > max_quantity_for_brand(brand):
        return None
    with _connect() as conn:"""
    if "target_tier < min_tier_for_brand(brand)" not in text:
        if old_reserve_check not in text:
            raise SystemExit("reserve_items_by_tier minimum check not found")
        text = text.replace(old_reserve_check, new_reserve_check, 1)

    old_reseller_reserve = """    total_charge = round(unit_charge * quantity, 2)

    with _connect() as conn:
        reseller = conn.execute(
            "SELECT * FROM resellers WHERE id = ? AND active = 1",
            (reseller_id,),
        ).fetchone()"""
    new_reseller_reserve = """    total_charge = round(unit_charge * quantity, 2)
    if target_tier < min_tier_for_brand(brand):
        return None
    if quantity > max_quantity_for_brand(brand):
        return None

    with _connect() as conn:
        reseller = conn.execute(
            "SELECT * FROM resellers WHERE id = ? AND active = 1",
            (reseller_id,),
        ).fetchone()"""
    if "reserve_reseller_items_by_tier" in text and "target_tier < min_tier_for_brand(brand)" not in text.split("reserve_reseller_items_by_tier", 1)[1][:2500]:
        if old_reseller_reserve not in text:
            raise SystemExit("reserve_reseller_items_by_tier check block not found")
        text = text.replace(old_reseller_reserve, new_reseller_reserve, 1)

    path.write_text(text, encoding="utf-8")
    print("patched db.py")


def patch_app() -> None:
    path = SHOP / "app.py"
    text = path.read_text(encoding="utf-8")

    old_import = "from catalog_tiers import order_meets_minimum, min_quantity_for_tier"
    new_import = (
        "from catalog_tiers import max_quantity_for_brand, min_tier_for_brand, "
        "order_meets_minimum, min_quantity_for_tier"
    )
    if "min_tier_for_brand" not in text:
        text = text.replace(old_import, new_import, 1)

    old_validate = """    if not brand or tier <= 0:
        return jsonify({"ok": False, "error": "Invalid product selection"}), 400

    if not order_meets_minimum(tier, quantity):"""
    new_validate = """    if not brand or tier <= 0:
        return jsonify({"ok": False, "error": "Invalid product selection"}), 400

    brand_min_tier = min_tier_for_brand(brand)
    if tier < brand_min_tier:
        return jsonify(
            {
                "ok": False,
                "error": f"{brand} orders start at ${brand_min_tier:.0f} face value",
            }
        ), 400

    brand_max_qty = max_quantity_for_brand(brand)
    if quantity > brand_max_qty:
        return jsonify(
            {
                "ok": False,
                "error": f"{brand} orders are limited to {brand_max_qty} card per order",
            }
        ), 400

    if not order_meets_minimum(tier, quantity):"""
    if "brand_min_tier = min_tier_for_brand(brand)" not in text:
        if old_validate not in text:
            raise SystemExit("create_order validation block not found")
        text = text.replace(old_validate, new_validate, 1)

    path.write_text(text, encoding="utf-8")
    print("patched app.py")


def patch_resellers() -> None:
    path = SHOP / "resellers.py"
    text = path.read_text(encoding="utf-8")

    old_import = "from catalog_tiers import nearest_tier"
    new_import = "from catalog_tiers import max_quantity_for_brand, min_tier_for_brand, nearest_tier"
    if "min_tier_for_brand" not in text:
        text = text.replace(old_import, new_import, 1)

    old_allowed = """def is_allowed_tier(brand: str, tier: float) -> bool:
    face = nearest_tier(tier)
    cap = max_face_for_brand(brand)
    if cap is not None and face > cap:
        return False
    return face > 0"""
    new_allowed = """def is_allowed_tier(brand: str, tier: float) -> bool:
    face = nearest_tier(tier)
    if face < min_tier_for_brand(brand):
        return False
    cap = max_face_for_brand(brand)
    if cap is not None and face > cap:
        return False
    return face > 0"""
    if "face < min_tier_for_brand(brand)" not in text:
        if old_allowed not in text:
            raise SystemExit("is_allowed_tier block not found")
        text = text.replace(old_allowed, new_allowed, 1)

    old_qty = "    qty = max(1, min(MAX_ORDER_QUANTITY, int(quantity or 1)))"
    new_qty = "    qty = max(1, min(max_quantity_for_brand(brand), int(quantity or 1)))"
    if "max_quantity_for_brand(brand)" not in text:
        if old_qty not in text:
            raise SystemExit("reseller qty cap not found")
        text = text.replace(old_qty, new_qty, 1)

    path.write_text(text, encoding="utf-8")
    print("patched resellers.py")


def patch_miniapp() -> None:
    path = SHOP / "static/miniapp/app.js"
    text = path.read_text(encoding="utf-8")

    if "brandMaxOrderQty" in text:
        print("miniapp already patched")
        return

    helper = """
function brandMaxOrderQty(brand) {
  const n = Number(brand?.max_order_quantity);
  if (n > 0) return n;
  return MAX_ORDER_QTY;
}

"""
    anchor = "const MAX_ORDER_QTY = 20;\n"
    if anchor not in text:
        raise SystemExit("MAX_ORDER_QTY anchor not found in app.js")
    text = text.replace(anchor, anchor + helper, 1)

    text = text.replace(
        "  const maxQty = Math.max(floor, Math.min(MAX_ORDER_QTY, maxStock || 1));",
        "  const maxQty = Math.max(floor, Math.min(brandMaxOrderQty(currentBrand), maxStock || 1));",
        1,
    )
    text = text.replace(
        "    Math.min(Number(qtySelect?.value) || 1, t.stock, MAX_ORDER_QTY)",
        "    Math.min(Number(qtySelect?.value) || 1, t.stock, brandMaxOrderQty(currentBrand))",
        1,
    )
    text = text.replace(
        "        quantity: Math.max(1, Math.min(Number(qtySelect?.value) || 1, t.stock, MAX_ORDER_QTY)),",
        "        quantity: Math.max(1, Math.min(Number(qtySelect?.value) || 1, t.stock, brandMaxOrderQty(currentBrand))),",
        1,
    )
    text = text.replace(
        "  const maxQty = Math.max(1, Math.min(MAX_ORDER_QTY, maxStock));",
        "  const maxQty = Math.max(1, Math.min(brandMaxOrderQty(resellerCurrentBrand), maxStock));",
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("patched static/miniapp/app.js")


def main() -> None:
    patch_catalog_tiers()
    patch_db()
    patch_app()
    patch_resellers()
    patch_miniapp()
    subprocess.run(
        [str(SHOP / "venv/bin/python"), "-c", "import catalog_tiers, db, app, resellers; print('import ok')"],
        check=True,
        cwd=SHOP,
    )
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")


if __name__ == "__main__":
    main()
