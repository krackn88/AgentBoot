"""Reseller credit grabs for allowed brands at custom pricing."""

from __future__ import annotations

from typing import Any

import cooper_log
import db
import payment_jobs
from catalog_tiers import nearest_tier
from config import MAX_ORDER_QUANTITY

RESELLER_ALLOWED_BRANDS = frozenset(
    {
        "Cracker Barrel",
        "Five Below",
        "Firehouse Subs",
    }
)
RESELLER_MAX_FACE_VALUE = 50.0


def is_allowed_brand(brand: str) -> bool:
    return brand in RESELLER_ALLOWED_BRANDS


def is_allowed_tier(tier: float) -> bool:
    return nearest_tier(tier) <= RESELLER_MAX_FACE_VALUE


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
        if brand not in RESELLER_ALLOWED_BRANDS:
            continue
        tiers = []
        for tier in db.list_brand_tiers(brand):
            face = float(tier["tier"])
            if face > RESELLER_MAX_FACE_VALUE:
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
        "allowed_brands": sorted(RESELLER_ALLOWED_BRANDS),
        "max_face_value": RESELLER_MAX_FACE_VALUE,
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
    if not is_allowed_brand(brand):
        raise ValueError("Brand not available for resellers")
    target_tier = nearest_tier(float(tier or 0))
    if target_tier <= 0 or not is_allowed_tier(target_tier):
        raise ValueError(f"Resellers can only grab hits up to ${RESELLER_MAX_FACE_VALUE:.0f}")

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
