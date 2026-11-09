#!/usr/bin/env python3
"""Charge and fulfill customer-selected tiers exactly; upgrade face only when needed."""

from __future__ import annotations

import subprocess
from pathlib import Path

SHOP = Path("/opt/giftcard-shop")
PATCHES = SHOP / "patches"


def patch_catalog_tiers() -> None:
    path = SHOP / "catalog_tiers.py"
    text = path.read_text(encoding="utf-8")
    if "inventory_fulfills_tier" in text:
        print("catalog_tiers already patched")
        return

    text = text.replace(
        "from config import MIN_ORDER_AMOUNT\n",
        "from config import MIN_ORDER_AMOUNT\nfrom pricing import calculate_price\n",
    )

    insert_after = "def nearest_tier(balance: float) -> float:\n"
    helper = '''def inventory_fulfills_tier(denomination: float, target_tier: float) -> bool:
    """Whether inventory can satisfy a customer who asked for target_tier face value."""
    denom = float(denomination)
    target = float(target_tier)
    if denom + 0.009 < target:
        return False
    if abs(denom - target) <= 0.02:
        return True
    if nearest_tier(denom) == target:
        return True
    return denom >= target


def inventory_selection_rank(denomination: float, target_tier: float) -> tuple[int, float, float]:
    """Lower is better: exact face, same bucket, then smallest upgrade."""
    denom = float(denomination)
    target = float(target_tier)
    if abs(denom - target) <= 0.02:
        phase = 0
    elif nearest_tier(denom) == target:
        phase = 1
    elif denom >= target:
        phase = 2
    else:
        phase = 99
    return (phase, abs(denom - target), denom)


'''
    idx = text.index(insert_after) + len(insert_after)
    end = text.index("\n\n", idx)
    text = text[:end] + "\n\n" + helper + text[end:]

    old_build = '''def build_tiers_from_rows(rows: list[dict[str, Any]], *, brand: str = "") -> list[dict[str, Any]]:
    buckets: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tier = nearest_tier(float(row["denomination"]))
        buckets[tier].append(row)

    tiers: list[dict[str, Any]] = []
    for tier_val, items in buckets.items():
        prices = [float(i["price"]) for i in items]
        balances = [float(i["denomination"]) for i in items]
        label = tier_display_labels(brand, tier_val) if brand else (
            "Under $10 Gift Card" if tier_val == 5 else f"${tier_val:.0f} Gift Card"
        )
        tiers.append(
            {
                "tier": tier_val,
                "label": label,
                "stock": len(items),
                "min_quantity": min_quantity_for_tier(tier_val),
                "price_from": round(min(prices), 2),
                "price_to": round(max(prices), 2),
                "balance_min": round(min(balances), 2),
                "balance_max": round(max(balances), 2),
            }
        )'''

    new_build = '''def build_tiers_from_rows(rows: list[dict[str, Any]], *, brand: str = "") -> list[dict[str, Any]]:
    candidate_tiers = {5.0, *STANDARD_TIERS}
    tiers: list[dict[str, Any]] = []
    for tier_val in sorted(candidate_tiers, reverse=True):
        fulfillable = [
            row for row in rows if inventory_fulfills_tier(float(row["denomination"]), tier_val)
        ]
        if not fulfillable:
            continue
        balances = [float(i["denomination"]) for i in fulfillable]
        tier_price = calculate_price(brand, tier_val) if brand else round(tier_val * 0.3, 2)
        label = tier_display_labels(brand, tier_val) if brand else (
            "Under $10 Gift Card" if tier_val == 5 else f"${tier_val:.0f} Gift Card"
        )
        tiers.append(
            {
                "tier": tier_val,
                "label": label,
                "stock": len(fulfillable),
                "min_quantity": min_quantity_for_tier(tier_val),
                "price_from": round(tier_price, 2),
                "price_to": round(tier_price, 2),
                "balance_min": round(min(balances), 2),
                "balance_max": round(max(balances), 2),
            }
        )'''

    if old_build not in text:
        raise SystemExit("build_tiers_from_rows block not found")
    text = text.replace(old_build, new_build, 1)
    path.write_text(text, encoding="utf-8")
    print("patched catalog_tiers.py")


def patch_db() -> None:
    path = SHOP / "db.py"
    text = path.read_text(encoding="utf-8")

    if "def select_inventory_for_tier" not in text:
        helper = '''

def select_inventory_for_tier(
    rows: list[sqlite3.Row],
    target_tier: float,
    quantity: int,
    *,
    exclude_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    from catalog_tiers import inventory_fulfills_tier, inventory_selection_rank

    excluded = exclude_ids or set()
    eligible: list[tuple[tuple[int, float, float], sqlite3.Row]] = []
    for row in rows:
        inv_id = int(row["id"])
        if inv_id in excluded:
            continue
        denom = float(row["denomination"])
        if not inventory_fulfills_tier(denom, target_tier):
            continue
        phase, distance, face = inventory_selection_rank(denom, target_tier)
        if phase == 99:
            continue
        eligible.append(((phase, distance, face), row))
    eligible.sort(key=lambda item: (item[0][0], item[0][1], item[0][2], int(item[1]["id"])))
    picked = [dict(item[1]) for item in eligible[: max(1, int(quantity))]]
    return picked


'''
        anchor = "\ndef reserve_items_by_tier("
        text = text.replace(anchor, helper + anchor, 1)

    old_reserve = '''        matches: list[sqlite3.Row] = []
        for row in rows:
            if nearest_tier(float(row["denomination"])) == target_tier:
                matches.append(row)
            if len(matches) >= quantity:
                break
        if len(matches) < quantity:
            return None

        first = matches[0]
        denomination = float(first["denomination"])
        total_price = round(sum(float(r["price"]) for r in matches), 2)
        inv_id = int(first["id"])'''

    new_reserve = '''        matches = select_inventory_for_tier(rows, target_tier, quantity)
        if len(matches) < quantity:
            return None

        first = matches[0]
        denomination = float(target_tier)
        unit_price = calculate_price(brand, target_tier)
        total_price = round(unit_price * quantity, 2)
        inv_id = int(first["id"])'''

    if old_reserve not in text:
        raise SystemExit("reserve_items_by_tier block not found")
    text = text.replace(old_reserve, new_reserve, 1)

    old_reassign = '''        matches: list[sqlite3.Row] = []
        for row in rows:
            if nearest_tier(float(row["denomination"])) == target_tier:
                matches.append(row)
            if len(matches) >= qty:
                break
        if len(matches) < qty:
            return {"ok": False, "error": "Not enough cards in stock for that amount"}

        total_price = round(sum(float(r["price"]) for r in matches), 2)
        if total_price > paid + 0.009:
            return {
                "ok": False,
                "error": (
                    f"That amount costs ${total_price:.2f} but you paid ${paid:.2f}. "
                    "Choose a lower tier or contact support."
                ),
            }

        _release_order_inventory(conn, order_id)

        first = matches[0]
        denomination = float(first["denomination"])'''

    new_reassign = '''        matches = select_inventory_for_tier(rows, target_tier, qty)
        if len(matches) < qty:
            return {"ok": False, "error": "Not enough cards in stock for that amount"}

        total_price = round(calculate_price(brand, target_tier) * qty, 2)
        if total_price > paid + 0.009:
            return {
                "ok": False,
                "error": (
                    f"That amount costs ${total_price:.2f} but you paid ${paid:.2f}. "
                    "Choose a lower tier or contact support."
                ),
            }

        _release_order_inventory(conn, order_id)

        first = matches[0]
        denomination = float(target_tier)'''

    if old_reassign in text:
        text = text.replace(old_reassign, new_reassign, 1)

    old_balance = '''        conn.execute(
            "UPDATE orders SET denomination = ?, price = ? WHERE inventory_id = ?",
            (balance, price, inv_id),
        )'''
    new_balance = '''        # Keep customer-facing order amount fixed after checkout.'''
    if old_balance in text:
        text = text.replace(old_balance, new_balance, 1)

    # reseller reserve block
    old_reseller = '''        matches: list = []
        for row in rows:
            if nearest_tier(float(row["denomination"])) == target_tier:
                matches.append(row)
            if len(matches) >= quantity:
                break
        if len(matches) < quantity:
            return None

        first = matches[0]
        denomination = float(first["denomination"])'''
    new_reseller = '''        matches = select_inventory_for_tier(rows, target_tier, quantity)
        if len(matches) < quantity:
            return None

        first = matches[0]
        denomination = float(target_tier)'''
    if old_reseller in text:
        text = text.replace(old_reseller, new_reseller, 1)

    old_find = '''    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, denomination, price, source_profile, source_key
            FROM inventory
            WHERE status = 'available' AND brand = ? AND denomination >= ? AND price > 0
            ORDER BY denomination DESC, id ASC
            """,
            (brand, min_bal if mode == "fallback" else max(min_bal, target)),
        ).fetchall()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        inv_id = int(row["id"])
        if inv_id in excluded:
            continue
        denom = float(row["denomination"])
        if mode == "primary":
            if denom < target or denom > hi:
                continue
            if nearest_tier(denom) != target_tier:
                continue
        elif mode == "fallback":
            if denom >= target or denom < min_bal:
                continue
        else:
            if nearest_tier(denom) != target_tier:
                continue
        candidates.append(dict(row))

    if not candidates:
        return None

    if mode == "primary":
        candidates.sort(key=lambda r: fulfillment.rank_primary_candidate(r, target))
    elif mode == "fallback":
        candidates.sort(key=lambda r: fulfillment.rank_fallback_candidate(r, target))
    return candidates[0]'''

    new_find = '''    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, denomination, price, source_profile, source_key
            FROM inventory
            WHERE status = 'available' AND brand = ? AND denomination >= ? AND price > 0
            ORDER BY denomination ASC, id ASC
            """,
            (brand, MIN_HIT_BALANCE),
        ).fetchall()

    if mode == "primary":
        picked = select_inventory_for_tier(rows, target_tier, 1, exclude_ids=excluded)
        return picked[0] if picked else None

    candidates: list[dict[str, Any]] = []
    for row in rows:
        inv_id = int(row["id"])
        if inv_id in excluded:
            continue
        denom = float(row["denomination"])
        if mode == "fallback":
            if denom >= target or denom < min_bal:
                continue
        else:
            if nearest_tier(denom) != target_tier:
                continue
        candidates.append(dict(row))

    if not candidates:
        return None

    if mode == "fallback":
        candidates.sort(key=lambda r: fulfillment.rank_fallback_candidate(r, target))
    return candidates[0]'''

    if old_find in text:
        text = text.replace(old_find, new_find, 1)

    path.write_text(text, encoding="utf-8")
    print("patched db.py")


def main() -> None:
    shutil_copy = PATCHES / "tier_fulfillment.py"
    if shutil_copy.exists():
        (SHOP / "tier_fulfillment.py").write_text(shutil_copy.read_text(encoding="utf-8"), encoding="utf-8")
    patch_catalog_tiers()
    patch_db()
    subprocess.run(
        [str(SHOP / "venv/bin/python"), "-c", "import catalog_tiers, db; print('import ok')"],
        check=True,
        cwd=SHOP,
    )
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")


if __name__ == "__main__":
    main()
