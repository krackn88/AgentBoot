#!/usr/bin/env python3
"""One-off: send order #35 customer a single $25 Firebirds card and close out."""

from __future__ import annotations

import sqlite3
import sys
import time

sys.path.insert(0, "/opt/giftcard-shop")

import db
import telegram_bot as tg
from config import DB_PATH
from crypto_util import decrypt_secret

ORDER_ID = 35
CHAT_ID = 883399717


def main() -> None:
    order = db.get_order(ORDER_ID)
    if not order:
        raise SystemExit(f"order #{ORDER_ID} not found")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT i.id, i.card_number_enc, i.pin_enc, i.denomination
        FROM order_items oi
        JOIN inventory i ON i.id = oi.inventory_id
        WHERE oi.order_id = ? AND oi.status = 'sold'
        ORDER BY oi.item_index ASC
        LIMIT 1
        """,
        (ORDER_ID,),
    ).fetchone()
    if not row:
        raise SystemExit("no sold card on order")

    card = decrypt_secret(row["card_number_enc"])
    balance = float(row["denomination"])

    tg.send_message(
        CHAT_ID,
        (
            f"<b>Order #{ORDER_ID} — final delivery</b>\n\n"
            "Sorry for the delay and confusion on this order. "
            "Here is your <b>$25 Firebirds</b> gift card. "
            "This completes your order — no further cards will be sent."
        ),
    )
    tg.deliver_firebirds_card(
        chat_id=CHAT_ID,
        card_number=card,
        balance=balance,
        order_id=ORDER_ID,
        verified=True,
    )

    now = time.time()
    with db._connect() as conn2:
        conn2.execute(
            "UPDATE orders SET quantity = 1, denomination = ?, status = 'delivered', "
            "delivered_at = ?, payment_status = 'confirmed' WHERE id = ?",
            (balance, now, ORDER_ID),
        )
        conn2.commit()

    print(f"sent ${balance:.2f} Firebirds card inv#{row['id']} to chat {CHAT_ID}")


if __name__ == "__main__":
    main()
