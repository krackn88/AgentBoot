#!/usr/bin/env python3
from pathlib import Path

path = Path("/opt/giftcard-shop/db.py")
text = path.read_text(encoding="utf-8")
marker = "picked = select_inventory_for_tier(rows, target_tier, 1, exclude_ids=excluded)"
if marker in text:
    print("already patched")
    raise SystemExit(0)

old = """    with _connect() as conn:
        rows = conn.execute(
            \"\"\"
            SELECT id, denomination, price, source_profile, source_key
            FROM inventory
            WHERE status = 'available' AND brand = ? AND denomination >= ? AND price > 0
            ORDER BY denomination DESC, id ASC
            \"\"\",
            (brand, min_bal if mode == \"fallback\" else max(min_bal, target)),
        ).fetchall()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        inv_id = int(row[\"id\"])
        if inv_id in excluded:
            continue
        denom = float(row[\"denomination\"])
        if mode == \"primary\":
            if denom < target or denom > hi:
                continue
            if nearest_tier(denom) != target_tier:
                continue
        elif mode == \"fallback\":
            if denom >= target or denom < min_bal:
                continue
        else:
            if nearest_tier(denom) != target_tier:
                continue
        candidates.append(dict(row))

    if not candidates:
        return None

    if mode == \"primary\":
        candidates.sort(key=lambda r: fulfillment.rank_primary_candidate(r, target))
    elif mode == \"fallback\":
        candidates.sort(key=lambda r: fulfillment.rank_fallback_candidate(r, target))
    return candidates[0]"""

new = """    with _connect() as conn:
        rows = conn.execute(
            \"\"\"
            SELECT id, denomination, price, source_profile, source_key
            FROM inventory
            WHERE status = 'available' AND brand = ? AND denomination >= ? AND price > 0
            ORDER BY denomination ASC, id ASC
            \"\"\",
            (brand, MIN_HIT_BALANCE),
        ).fetchall()

    if mode == \"primary\":
        picked = select_inventory_for_tier(rows, target_tier, 1, exclude_ids=excluded)
        return picked[0] if picked else None

    candidates: list[dict[str, Any]] = []
    for row in rows:
        inv_id = int(row[\"id\"])
        if inv_id in excluded:
            continue
        denom = float(row[\"denomination\"])
        if mode == \"fallback\":
            if denom >= target or denom < min_bal:
                continue
        else:
            if nearest_tier(denom) != target_tier:
                continue
        candidates.append(dict(row))

    if not candidates:
        return None

    if mode == \"fallback\":
        candidates.sort(key=lambda r: fulfillment.rank_fallback_candidate(r, target))
    return candidates[0]"""

if old not in text:
    raise SystemExit("block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("patched")
