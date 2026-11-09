#!/usr/bin/env python3
"""Patch giftr shop so admins can view reseller tab with all credit/orders."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

PATCHES = Path(__file__).resolve().parent
SHOP = Path("/opt/giftcard-shop")


def patch_file(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"patch miss in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path}")


def append_db_function() -> None:
    db_path = SHOP / "db.py"
    text = db_path.read_text(encoding="utf-8")
    marker = "def list_reseller_orders("
    if marker in text:
        print("skip db list_reseller_orders")
        return
    block = """
def list_reseller_orders(
    telegram_user_id: int | None = None,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with _connect() as conn:
        if telegram_user_id is not None:
            rows = conn.execute(
                \"\"\"
                SELECT
                    o.*,
                    r.name AS reseller_name,
                    r.pricing_percentage AS reseller_pricing
                FROM orders o
                LEFT JOIN resellers r ON r.telegram_user_id = o.telegram_user_id
                WHERE o.payment_status = 'reseller_credit'
                  AND o.telegram_user_id = ?
                ORDER BY o.id DESC
                LIMIT ?
                \"\"\",
                (int(telegram_user_id), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                \"\"\"
                SELECT
                    o.*,
                    r.name AS reseller_name,
                    r.pricing_percentage AS reseller_pricing
                FROM orders o
                LEFT JOIN resellers r ON r.telegram_user_id = o.telegram_user_id
                WHERE o.payment_status = 'reseller_credit'
                ORDER BY o.id DESC
                LIMIT ?
                \"\"\",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


"""
    insert_at = text.index("def refund_reseller_credit(")
    db_path.write_text(text[:insert_at] + block + text[insert_at:], encoding="utf-8")
    print("appended list_reseller_orders to db.py")


def replace_reseller_js() -> None:
    app_js = SHOP / "static/miniapp/app.js"
    text = app_js.read_text(encoding="utf-8")
    start = text.find("// --- Reseller tab (appended) ---")
    if start < 0:
        raise SystemExit("reseller js block not found")
    new_block = (PATCHES / "reseller_miniapp.js").read_text(encoding="utf-8")
    app_js.write_text(text[:start] + new_block.strip() + "\n", encoding="utf-8")
    print("replaced reseller miniapp js")


def main() -> int:
    shutil.copy2(PATCHES / "resellers.py", SHOP / "resellers.py")

    append_db_function()

    patch_file(
        SHOP / "app.py",
        '''@app.get("/api/reseller/me")
def reseller_me():
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id:
        return jsonify({"ok": False, "error": "Telegram user required"}), 400
    reseller = resellers.get_active_reseller(int(user_id))
    if not reseller:
        return jsonify({"ok": True, "reseller": None})
    return jsonify({"ok": True, "reseller": resellers.reseller_me_payload(reseller)})''',
        '''@app.get("/api/reseller/me")
def reseller_me():
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id:
        return jsonify({"ok": False, "error": "Telegram user required"}), 400
    uid = int(user_id)
    is_admin = _is_admin_telegram_user(uid)
    reseller = resellers.get_active_reseller(uid)
    payload: dict = {
        "ok": True,
        "reseller": resellers.reseller_me_payload(reseller) if reseller else None,
        "is_admin": is_admin,
    }
    if is_admin:
        payload["admin_overview"] = resellers.admin_overview()
    return jsonify(payload)''',
    )

    patch_file(
        SHOP / "app.py",
        '''    reseller = resellers.get_active_reseller(int(user_id))
    if not reseller:
        return jsonify({"ok": False, "error": "Not a reseller"}), 403
    return jsonify(
        {
            "ok": True,
            "reseller": resellers.reseller_me_payload(reseller),
            "brands": resellers.list_catalog_for_reseller(),
        }
    )''',
        '''    uid = int(user_id)
    is_admin = _is_admin_telegram_user(uid)
    reseller = resellers.get_active_reseller(uid)
    if not reseller and not is_admin:
        return jsonify({"ok": False, "error": "Not a reseller"}), 403
    return jsonify(
        {
            "ok": True,
            "reseller": resellers.reseller_me_payload(reseller) if reseller else None,
            "is_admin": is_admin,
            "brands": resellers.list_catalog_for_reseller(),
            "admin_overview": resellers.admin_overview() if is_admin else None,
        }
    )''',
    )

    patch_file(
        SHOP / "app.py",
        '''    return jsonify({"ok": True, "reseller": row})


@app.post("/api/telegram/webhook")''',
        '''    return jsonify({"ok": True, "reseller": row})


@app.get("/api/admin/reseller-orders")
def admin_reseller_orders():
    if not _admin_ok():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    limit = min(500, max(1, int(request.args.get("limit") or 100)))
    orders = [resellers.serialize_reseller_order(o) for o in db.list_reseller_orders(limit=limit)]
    return jsonify({"ok": True, "orders": orders})


@app.get("/api/reseller/orders")
def reseller_orders():
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id:
        return jsonify({"ok": False, "error": "Telegram user required"}), 400
    uid = int(user_id)
    is_admin = _is_admin_telegram_user(uid)
    reseller = resellers.get_active_reseller(uid)
    if not reseller and not is_admin:
        return jsonify({"ok": False, "error": "Not a reseller"}), 403
    if is_admin:
        orders = db.list_reseller_orders(limit=100)
    else:
        orders = db.list_reseller_orders(telegram_user_id=uid, limit=100)
    return jsonify(
        {
            "ok": True,
            "is_admin": is_admin,
            "orders": [resellers.serialize_reseller_order(o) for o in orders],
        }
    )


@app.post("/api/telegram/webhook")''',
    )

    index = SHOP / "static/miniapp/index.html"
    html = index.read_text(encoding="utf-8")
    if 'id="reseller-admin-overview"' not in html:
        html = html.replace(
            '        <h2>Reseller grabs</h2>\n        <p class="muted">All brands · Cracker Barrel / Five Below / Firehouse capped at $50</p>',
            '        <h2 id="reseller-header-title">Reseller grabs</h2>\n        <p id="reseller-header-sub" class="muted">All brands · Cracker Barrel / Five Below / Firehouse capped at $50</p>',
        )
        html = html.replace(
            '      <div id="reseller-account" class="reseller-account"></div>\n      <div id="reseller-brands" class="brand-grid"></div>',
            '      <div id="reseller-admin-overview" class="reseller-admin-overview hidden"></div>\n'
            '      <div id="reseller-account" class="reseller-account"></div>\n'
            '      <div id="reseller-grab-section">\n'
            '      <div id="reseller-brands" class="brand-grid"></div>',
        )
        html = html.replace(
            '        <p id="reseller-grab-msg" class="muted"></p>\n      </section>\n      <button type="button" id="reseller-view-back"',
            '        <p id="reseller-grab-msg" class="muted"></p>\n      </section>\n      </div>\n      <button type="button" id="reseller-view-back"',
        )
        index.write_text(html, encoding="utf-8")
        print("patched index.html")

    css = SHOP / "static/miniapp/style.css"
    css_block = """
.reseller-admin-overview {
  margin-bottom: 16px;
}

.reseller-admin-section h3 {
  margin: 0 0 10px;
  font-size: 1rem;
}

.reseller-admin-grid {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}

.reseller-admin-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 14px;
}

.reseller-admin-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.reseller-pill {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 999px;
}

.reseller-pill.ok { background: #d4edda; color: #155724; }
.reseller-pill.bad { background: #f8d7da; color: #721c24; }

.reseller-orders-list {
  display: grid;
  gap: 10px;
}

.reseller-order-row {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 0.9rem;
}
"""
    if ".reseller-admin-overview" not in css.read_text(encoding="utf-8"):
        css.write_text(css.read_text(encoding="utf-8").rstrip() + css_block, encoding="utf-8")
        print("patched style.css")

    admin = SHOP / "templates/admin.html"
    admin_text = admin.read_text(encoding="utf-8")
    if "reseller-orders-body" not in admin_text:
        admin_text = admin_text.replace(
            "        <tbody id=\"resellers-body\"></tbody>\n      </table>\n    </section>",
            "        <tbody id=\"resellers-body\"></tbody>\n      </table>\n"
            "      <h3 style=\"margin-top:20px\">Reseller orders</h3>\n"
            "      <button onclick=\"loadResellerOrders()\">Refresh orders</button>\n"
            "      <table>\n"
            "        <thead><tr><th>ID</th><th>When</th><th>Reseller</th><th>Product</th><th>Charged</th><th>Status</th></tr></thead>\n"
            "        <tbody id=\"reseller-orders-body\"></tbody>\n"
            "      </table>\n"
            "    </section>",
        )
        if "async function loadResellerOrders" not in admin_text:
            admin_text = admin_text.replace(
                "    loadResellers();",
                "    loadResellers();\n    loadResellerOrders();",
            )
            admin_text = admin_text.replace(
                "    async function toggleReseller(id, active) {",
                "    async function loadResellerOrders() {\n"
                "      const res = await adminFetch('/api/admin/reseller-orders?limit=200');\n"
                "      const data = await res.json();\n"
                "      document.getElementById('reseller-orders-body').innerHTML = (data.orders || []).map((o) => {\n"
                "        const qty = Number(o.quantity || 1);\n"
                "        const product = `${o.brand} $${Number(o.denomination).toFixed(2)}${qty > 1 ? ` × ${qty}` : ''}`;\n"
                "        const who = o.reseller_name || o.telegram_first_name || o.telegram_user_id;\n"
                "        return `<tr>\n"
                "          <td>#${o.id}</td>\n"
                "          <td>${fmtTime(o.created_at)}</td>\n"
                "          <td>${who}<br><span class=\"muted\">${o.telegram_user_id}</span></td>\n"
                "          <td>${product}</td>\n"
                "          <td>$${Number(o.price).toFixed(2)}</td>\n"
                "          <td>${o.status}</td>\n"
                "        </tr>`;\n"
                "      }).join('') || '<tr><td colspan=\"6\" class=\"muted\">No reseller orders yet.</td></tr>';\n"
                "    }\n\n"
                "    async function toggleReseller(id, active) {",
            )
        admin.write_text(admin_text, encoding="utf-8")
        print("patched admin.html")

    replace_reseller_js()

    subprocess.run(
        [str(SHOP / "venv/bin/python"), "-c", "import db, resellers; db.init_db(); print('ok')"],
        check=True,
        cwd=SHOP,
    )
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
