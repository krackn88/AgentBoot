"""Database helpers for reseller accounts — appended to db.py on deploy."""

from __future__ import annotations

import time
from typing import Any

from catalog_tiers import nearest_tier

# Paste these functions into db.py (deploy script handles insertion).


def _init_resellers_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS resellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            telegram_user_id INTEGER NOT NULL UNIQUE,
            pricing_percentage REAL NOT NULL,
            credit_balance REAL NOT NULL DEFAULT 0,
            credit_limit REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            notes TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resellers_telegram ON resellers(telegram_user_id)"
    )
    existing = conn.execute(
        "SELECT 1 FROM resellers WHERE telegram_user_id = ?",
        (7864109299,),
    ).fetchone()
    if not existing:
        conn.execute(
            """
            INSERT INTO resellers
            (name, telegram_user_id, pricing_percentage, credit_balance, credit_limit, active, created_at, notes)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                "Esco",
                7864109299,
                0.175,
                200.0,
                200.0,
                time.time(),
                "Initial reseller",
            ),
        )


def get_reseller_by_telegram_id(telegram_user_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM resellers WHERE telegram_user_id = ?",
            (int(telegram_user_id),),
        ).fetchone()
    return dict(row) if row else None


def get_reseller(reseller_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM resellers WHERE id = ?",
            (int(reseller_id),),
        ).fetchone()
    return dict(row) if row else None


def list_resellers() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM resellers ORDER BY name COLLATE NOCASE, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def create_reseller(
    *,
    name: str,
    telegram_user_id: int,
    pricing_percentage: float,
    credit_balance: float = 0.0,
    credit_limit: float = 0.0,
    notes: str | None = None,
    active: bool = True,
) -> dict[str, Any]:
    now = time.time()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO resellers
            (name, telegram_user_id, pricing_percentage, credit_balance, credit_limit, active, created_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                int(telegram_user_id),
                float(pricing_percentage),
                round(float(credit_balance), 2),
                round(float(credit_limit), 2),
                1 if active else 0,
                now,
                notes,
            ),
        )
        row = conn.execute(
            "SELECT * FROM resellers WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return dict(row) if row else {}


def update_reseller(reseller_id: int, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "name",
        "telegram_user_id",
        "pricing_percentage",
        "credit_balance",
        "credit_limit",
        "active",
        "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_reseller(reseller_id)
    if "credit_balance" in updates:
        updates["credit_balance"] = round(float(updates["credit_balance"]), 2)
    if "credit_limit" in updates:
        updates["credit_limit"] = round(float(updates["credit_limit"]), 2)
    if "pricing_percentage" in updates:
        updates["pricing_percentage"] = float(updates["pricing_percentage"])
    if "telegram_user_id" in updates:
        updates["telegram_user_id"] = int(updates["telegram_user_id"])
    if "active" in updates:
        updates["active"] = 1 if updates["active"] else 0
    if "name" in updates:
        updates["name"] = str(updates["name"]).strip()

    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [int(reseller_id)]
    with _connect() as conn:
        conn.execute(f"UPDATE resellers SET {cols} WHERE id = ?", vals)
        row = conn.execute(
            "SELECT * FROM resellers WHERE id = ?",
            (int(reseller_id),),
        ).fetchone()
    return dict(row) if row else None


def refund_reseller_credit(reseller_id: int, amount: float, *, order_id: int | None = None) -> None:
    amt = round(float(amount), 2)
    if amt <= 0:
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE resellers SET credit_balance = credit_balance + ? WHERE id = ?",
            (amt, int(reseller_id)),
        )


def reserve_reseller_items_by_tier(
    reseller_id: int,
    brand: str,
    tier: float,
    telegram_user_id: int,
    telegram_username: str | None,
    telegram_first_name: str | None,
    pricing_percentage: float,
    *,
    quantity: int = 1,
) -> dict[str, Any] | None:
    from config import MAX_ORDER_QUANTITY
    from resellers import is_allowed_tier

    quantity = max(1, min(MAX_ORDER_QUANTITY, int(quantity)))
    now = time.time()
    target_tier = nearest_tier(tier)
    if not is_allowed_tier(brand, target_tier):
        return None
    unit_charge = round(target_tier * float(pricing_percentage), 2)
    total_charge = round(unit_charge * quantity, 2)

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        reseller = conn.execute(
            "SELECT * FROM resellers WHERE id = ? AND active = 1",
            (int(reseller_id),),
        ).fetchone()
        if not reseller or float(reseller["credit_balance"]) < total_charge:
            return None

        rows = conn.execute(
            """
            SELECT id, denomination, price
            FROM inventory
            WHERE status = 'available' AND brand = ? AND denomination >= ?
            ORDER BY denomination DESC, id ASC
            """,
            (brand, MIN_HIT_BALANCE),
        ).fetchall()
        matches: list = []
        for row in rows:
            if nearest_tier(float(row["denomination"])) == target_tier:
                matches.append(row)
            if len(matches) >= quantity:
                break
        if len(matches) < quantity:
            return None

        first = matches[0]
        denomination = float(first["denomination"])

        deducted = conn.execute(
            """
            UPDATE resellers
            SET credit_balance = credit_balance - ?
            WHERE id = ? AND credit_balance >= ?
            """,
            (total_charge, int(reseller_id), total_charge),
        )
        if deducted.rowcount != 1:
            return None

        inv_id = int(first["id"])
        cur = conn.execute(
            """
            INSERT INTO orders
            (inventory_id, brand, denomination, price, quantity, telegram_user_id,
             telegram_username, telegram_first_name, status, created_at, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', ?, 'reseller_pending')
            """,
            (
                inv_id,
                brand,
                denomination,
                total_charge,
                quantity,
                telegram_user_id,
                telegram_username,
                telegram_first_name,
                now,
            ),
        )
        order_id = int(cur.lastrowid)

        for idx, row in enumerate(matches):
            item_inv_id = int(row["id"])
            reserved = conn.execute(
                """
                UPDATE inventory
                SET status = 'reserved', reserved_at = ?, order_id = ?
                WHERE id = ? AND status = 'available'
                """,
                (now, order_id, item_inv_id),
            )
            if reserved.rowcount != 1:
                conn.execute(
                    "UPDATE resellers SET credit_balance = credit_balance + ? WHERE id = ?",
                    (total_charge, int(reseller_id)),
                )
                return None
            conn.execute(
                """
                INSERT INTO order_items (order_id, inventory_id, item_index, status)
                VALUES (?, ?, ?, 'reserved')
                """,
                (order_id, item_inv_id, idx),
            )

        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(order) if order else None
