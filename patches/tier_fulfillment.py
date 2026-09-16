"""Customer tier matching: exact face first, small upgrade only when needed."""

from __future__ import annotations

from typing import Any

from catalog_tiers import nearest_tier

EXACT_FACE_TOLERANCE = 0.02


def inventory_fulfills_tier(denomination: float, target_tier: float) -> bool:
    """Whether a card can satisfy a customer who asked for target_tier face value."""
    denom = float(denomination)
    target = float(target_tier)
    if denom + 0.009 < target:
        return False
    if abs(denom - target) <= EXACT_FACE_TOLERANCE:
        return True
    if nearest_tier(denom) == target:
        return True
    return denom >= target


def inventory_selection_rank(denomination: float, target_tier: float) -> tuple[int, float, float, int]:
    """Lower is better: exact face, same bucket, then smallest upgrade."""
    denom = float(denomination)
    target = float(target_tier)
    if abs(denom - target) <= EXACT_FACE_TOLERANCE:
        phase = 0
    elif nearest_tier(denom) == target:
        phase = 1
    elif denom >= target:
        phase = 2
    else:
        phase = 99
    return (phase, abs(denom - target), denom, 0)


def select_inventory_for_tier(
    rows: list[Any],
    target_tier: float,
    quantity: int,
    *,
    exclude_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    excluded = exclude_ids or set()
    eligible: list[tuple[tuple[int, float, float, int], Any]] = []
    for row in rows:
        inv_id = int(row["id"])
        if inv_id in excluded:
            continue
        denom = float(row["denomination"])
        if not inventory_fulfills_tier(denom, target_tier):
            continue
        rank = inventory_selection_rank(denom, target_tier)
        if rank[0] == 99:
            continue
        eligible.append((rank, row))

    eligible.sort(key=lambda item: (item[0][0], item[0][1], item[0][2], int(item[1]["id"])))
    picked = [dict(item[1]) for item in eligible[: max(1, int(quantity))]]
    return picked
