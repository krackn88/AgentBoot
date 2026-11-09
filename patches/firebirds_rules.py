"""Brand-specific tier and quantity rules (reference copy for catalog_tiers helpers)."""

from __future__ import annotations

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
