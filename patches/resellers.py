"""Reseller credit grabs at custom pricing."""

from __future__ import annotations

from typing import Any

import cooper_log
import db
import payment_jobs
from catalog_tiers import nearest_tier
from config import MAX_ORDER_QUANTITY

# These brands are capped at $50 face for reseller grabs; all other brands have no cap.
RESELLER_CAPPED_BRANDS = frozenset(
    {
        "Cracker Barrel",
        "Five Below",
        "Firehouse Subs",
    }
)
RESELLER_CAPPED_MAX_FACE_VALUE = 50.0


def brand_has_face_cap(brand: str) -> bool:
    return brand in RESELLER_CAPPED_BRANDS


def max_face_for_brand(brand: str) -> float | None:
    if brand_has_face_cap(brand):
        return RESELLER_CAPPED_MAX_FACE_VALUE
    return None


def is_allowed_tier(brand: str, tier: float) -> bool:
    face = nearest_tier(tier)
    cap = max_face_for_brand(brand)
    if cap is not None and face > cap:
        return False
    return face > 0


def reseller_charge(face_value: float, quantity: int, pricing_percentage: float) -> float:
    tier = nearest_tier(face_value)
    qty = max(1, int(quantity))
    return round(tier * pricing_percentage * qty, 2)


def get_active_reseller(telegram_user_id: int) -> dict[str, Any] | None:
    row = db.get_reseller_by_telegram_id(telegram_user_id)
    if not row or not int(row.get("active") or 0):
        return None
    return row


def list_catalog_for_reseller() -> list[dict[str, Any]]:
    brands = []
    for brand_info in db.list_brands():
        brand = brand_info["brand"]
        cap = max_face_for_brand(brand)
        tiers = []
        for tier in db.list_brand_tiers(brand):
            face = float(tier["tier"])
            if cap is not None and face > cap:
                continue
            tiers.append(tier)
        if not tiers:
            continue
        brands.append(
            {
                **brand_info,
                "tiers": tiers,
                "tier_count": len(tiers),
                "stock": sum(int(t.get("stock") or 0) for t in tiers),
                "max_face_value": cap,
            }
        )
    return brands


def reseller_me_payload(reseller: dict[str, Any]) -> dict[str, Any]:
    pct = float(reseller["pricing_percentage"])
    return {
        "id": int(reseller["id"]),
        "name": reseller["name"],
        "telegram_user_id": int(reseller["telegram_user_id"]),
        "pricing_percentage": pct,
        "pricing_label": f"{pct * 100:.1f}%",
        "credit_balance": round(float(reseller["credit_balance"]), 2),
        "credit_limit": round(float(reseller.get("credit_limit") or 0), 2),
        "capped_brands": sorted(RESELLER_CAPPED_BRANDS),
        "capped_max_face_value": RESELLER_CAPPED_MAX_FACE_VALUE,
    }


def grab_hit(
    reseller: dict[str, Any],
    *,
    brand: str,
    tier: float,
    quantity: int,
    telegram_user_id: int,
    telegram_username: str | None,
    telegram_first_name: str | None,
) -> dict[str, Any]:
    brand = str(brand or "").strip()
    if not brand:
        raise ValueError("Brand required")

    target_tier = nearest_tier(float(tier or 0))
    if not is_allowed_tier(brand, target_tier):
        cap = max_face_for_brand(brand)
        if cap is not None:
            raise ValueError(f"{brand} reseller grabs are capped at ${cap:.0f} face value")
        raise ValueError("Invalid tier selection")

    qty = max(1, min(MAX_ORDER_QUANTITY, int(quantity or 1)))
    pricing_pct = float(reseller["pricing_percentage"])
    charge = reseller_charge(target_tier, qty, pricing_pct)
    credit = float(reseller["credit_balance"])
    if credit < charge:
        raise ValueError(
            f"Insufficient credit — need ${charge:.2f}, have ${credit:.2f}"
        )

    order = db.reserve_reseller_items_by_tier(
        reseller_id=int(reseller["id"]),
        brand=brand,
        tier=target_tier,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
        telegram_first_name=telegram_first_name,
        pricing_percentage=pricing_pct,
        quantity=qty,
    )
    if not order:
        raise ValueError("Not enough cards in stock for that quantity")

    order_id = int(order["id"])
    paid = db.mark_order_paid(order_id)
    if not paid:
        db.refund_reseller_credit(int(reseller["id"]), charge, order_id=order_id)
        db.cancel_order(order_id)
        raise RuntimeError("Reseller order setup failed")

    db.update_order_payment_status(order_id, "reseller_credit")
    cooper_log.log_reseller_grab(
        order_id=str(order_id),
        reseller_name=str(reseller.get("name") or ""),
        user_id=telegram_user_id,
        username=telegram_username,
        brand=brand,
        quantity=qty,
        face_value=target_tier * qty,
        charge_usd=charge,
        credit_remaining=round(credit - charge, 2),
    )
    payment_jobs.spawn_delivery(order_id)
    final = db.get_order(order_id) or paid
    return final
