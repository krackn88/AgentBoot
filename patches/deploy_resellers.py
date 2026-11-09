#!/usr/bin/env python3
"""Deploy reseller credit-grab feature to giftr shop on dedi."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PATCHES = Path(__file__).resolve().parent
SHOP = Path("/opt/giftcard-shop")


def patch_file(path: Path, replacements: list[tuple[str, str]], *, required: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in text:
            if required:
                raise SystemExit(f"patch miss in {path}: {old[:120]!r}")
            continue
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def append_if_missing(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"skip append {path} ({marker})")
        return
    path.write_text(text.rstrip() + "\n\n" + block.strip() + "\n", encoding="utf-8")
    print(f"appended to {path}")


def main() -> int:
    shutil.copy2(PATCHES / "resellers.py", SHOP / "resellers.py")

    # --- db.py: schema + reseller helpers ---
    patch_file(
        SHOP / "db.py",
        [
            (
                '        conn.execute(\n            "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)"\n        )\n        conn.execute(\n            """\n            INSERT INTO order_items',
                '        conn.execute(\n            "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)"\n        )\n        conn.execute(\n            """\n            CREATE TABLE IF NOT EXISTS resellers (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                name TEXT NOT NULL,\n                telegram_user_id INTEGER NOT NULL UNIQUE,\n                pricing_percentage REAL NOT NULL,\n                credit_balance REAL NOT NULL DEFAULT 0,\n                credit_limit REAL NOT NULL DEFAULT 0,\n                active INTEGER NOT NULL DEFAULT 1,\n                created_at REAL NOT NULL,\n                notes TEXT\n            )\n            """\n        )\n        conn.execute(\n            "CREATE INDEX IF NOT EXISTS idx_resellers_telegram ON resellers(telegram_user_id)"\n        )\n        if not conn.execute(\n            "SELECT 1 FROM resellers WHERE telegram_user_id = ?",\n            (7864109299,),\n        ).fetchone():\n            conn.execute(\n                """\n                INSERT INTO resellers\n                (name, telegram_user_id, pricing_percentage, credit_balance, credit_limit, active, created_at, notes)\n                VALUES (?, ?, ?, ?, ?, 1, ?, ?)\n                """,\n                ("Esco", 7864109299, 0.175, 200.0, 200.0, time.time(), "Initial reseller"),\n            )\n        conn.execute(\n            """\n            INSERT INTO order_items',
            ),
        ],
    )

    reseller_db_block = (PATCHES / "reseller_db.py").read_text(encoding="utf-8")
    # Strip header comment lines; keep only function defs from get_reseller_by_telegram_id onward
    start = reseller_db_block.index("def get_reseller_by_telegram_id")
    append_if_missing(SHOP / "db.py", "def get_reseller_by_telegram_id", reseller_db_block[start:])

    # --- cooper_log.py ---
    append_if_missing(
        SHOP / "cooper_log.py",
        "def log_reseller_grab",
        '''
def log_reseller_grab(
    *,
    order_id: str,
    reseller_name: str,
    user_id: int,
    username: Optional[str] = None,
    brand: str = "",
    quantity: int = 1,
    face_value: float = 0,
    charge_usd: float = 0,
    credit_remaining: float = 0,
) -> None:
    user_label = f"@{username}" if username else f"user_{user_id}"
    log_to_cooper(
        "\\n".join(
            [
                "🏷️ <b>GIFTR — RESELLER GRAB</b>",
                "",
                f"Order ID: <code>{order_id}</code>",
                f"Reseller: {reseller_name or 'n/a'} · {user_label} ({user_id})",
                f"Brand: {brand or 'n/a'} · qty {quantity} · face ${face_value:.2f}",
                f"Charged: ${charge_usd:.2f} · credit left ${credit_remaining:.2f}",
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
        )
    )
''',
    )

    # --- app.py ---
    patch_file(
        SHOP / "app.py",
        [
            (
                "import payment_jobs\n",
                "import payment_jobs\nimport resellers\n",
            ),
            (
                '        "admin_comp": admin_comp,\n    }\n    if include_payment and not admin_comp:',
                '        "admin_comp": admin_comp,\n        "reseller_credit": order.get("payment_status") == "reseller_credit",\n    }\n    if include_payment and not admin_comp and order.get("payment_status") != "reseller_credit":',
            ),
        ],
    )

    app_routes = '''
@app.get("/api/reseller/me")
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
    return jsonify({"ok": True, "reseller": resellers.reseller_me_payload(reseller)})


@app.get("/api/reseller/catalog")
def reseller_catalog():
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id:
        return jsonify({"ok": False, "error": "Telegram user required"}), 400
    reseller = resellers.get_active_reseller(int(user_id))
    if not reseller:
        return jsonify({"ok": False, "error": "Not a reseller"}), 403
    return jsonify(
        {
            "ok": True,
            "reseller": resellers.reseller_me_payload(reseller),
            "brands": resellers.list_catalog_for_reseller(),
        }
    )


@app.post("/api/reseller/grab")
def reseller_grab():
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id:
        return jsonify({"ok": False, "error": "Telegram user required"}), 400
    reseller = resellers.get_active_reseller(int(user_id))
    if not reseller:
        return jsonify({"ok": False, "error": "Not a reseller"}), 403

    data = request.get_json(force=True, silent=True) or {}
    brand = str(data.get("brand") or "").strip()
    try:
        tier = float(data.get("tier") or data.get("denomination") or 0)
        quantity = int(data.get("quantity") or 1)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid selection"}), 400

    try:
        order = resellers.grab_hit(
            reseller,
            brand=brand,
            tier=tier,
            quantity=quantity,
            telegram_user_id=int(user_id),
            telegram_username=user.get("username"),
            telegram_first_name=user.get("first_name"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        log.exception("Reseller grab failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

    updated = resellers.get_active_reseller(int(user_id))
    return jsonify(
        {
            "ok": True,
            "order": _order_api_payload(order, include_payment=False),
            "reseller": resellers.reseller_me_payload(updated) if updated else None,
        }
    )


@app.get("/api/admin/resellers")
def admin_list_resellers():
    if not _admin_ok():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    rows = db.list_resellers()
    out = []
    for r in rows:
        pct = float(r["pricing_percentage"])
        out.append(
            {
                "id": int(r["id"]),
                "name": r["name"],
                "telegram_user_id": int(r["telegram_user_id"]),
                "pricing_percentage": pct,
                "pricing_label": f"{pct * 100:.1f}%",
                "credit_balance": round(float(r["credit_balance"]), 2),
                "credit_limit": round(float(r.get("credit_limit") or 0), 2),
                "active": bool(int(r.get("active") or 0)),
                "created_at": r.get("created_at"),
                "notes": r.get("notes") or "",
            }
        )
    return jsonify({"ok": True, "resellers": out})


@app.post("/api/admin/resellers")
def admin_create_reseller():
    if not _admin_ok():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    try:
        telegram_user_id = int(data.get("telegram_user_id") or 0)
        pricing_percentage = float(data.get("pricing_percentage") or 0)
        credit_balance = float(data.get("credit_balance") or 0)
        credit_limit = float(data.get("credit_limit") or credit_balance)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid reseller fields"}), 400
    if not name or telegram_user_id <= 0 or pricing_percentage <= 0:
        return jsonify({"ok": False, "error": "Name, Telegram ID, and pricing % required"}), 400
    if pricing_percentage > 1:
        pricing_percentage = pricing_percentage / 100.0
    try:
        row = db.create_reseller(
            name=name,
            telegram_user_id=telegram_user_id,
            pricing_percentage=pricing_percentage,
            credit_balance=credit_balance,
            credit_limit=credit_limit,
            notes=str(data.get("notes") or "") or None,
            active=bool(data.get("active", True)),
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "reseller": row})


@app.put("/api/admin/resellers/<int:reseller_id>")
def admin_update_reseller(reseller_id: int):
    if not _admin_ok():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    fields = {}
    for key in ("name", "telegram_user_id", "credit_balance", "credit_limit", "notes", "active"):
        if key in data:
            fields[key] = data[key]
    if "pricing_percentage" in data:
        pct = float(data["pricing_percentage"])
        if pct > 1:
            pct = pct / 100.0
        fields["pricing_percentage"] = pct
    try:
        row = db.update_reseller(reseller_id, **fields)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not row:
        return jsonify({"ok": False, "error": "Reseller not found"}), 404
    return jsonify({"ok": True, "reseller": row})


'''
    patch_file(
        SHOP / "app.py",
        [
            (
                "@app.post(\"/api/telegram/webhook\")",
                app_routes + "\n@app.post(\"/api/telegram/webhook\")",
            ),
        ],
    )

    # --- miniapp index.html: nav + reseller view ---
    patch_file(
        SHOP / "static/miniapp/index.html",
        [
            (
                '        <button type="button" class="nav-item" data-nav="orders">',
                '        <button type="button" class="nav-item hidden" id="nav-reseller" data-nav="reseller">\n'
                '          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v10H4zM8 11h8M8 15h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>\n'
                '          <span>Reseller</span>\n'
                '        </button>\n'
                '        <button type="button" class="nav-item" data-nav="orders">',
            ),
            (
                '    <section id="help-view" class="hidden help-panel">',
                '    <section id="reseller-view" class="hidden reseller-panel">\n'
                '      <div class="reseller-header">\n'
                '        <h2>Reseller grabs</h2>\n'
                '        <p class="muted">All brands · Cracker Barrel / Five Below / Firehouse capped at $50</p>\n'
                '      </div>\n'
                '      <div id="reseller-account" class="reseller-account"></div>\n'
                '      <div id="reseller-brands" class="brand-grid"></div>\n'
                '      <section id="reseller-grab-panel" class="hidden purchase-box reseller-grab-box">\n'
                '        <button type="button" id="reseller-back-brands" class="back-link">← All reseller brands</button>\n'
                '        <div class="brand-hero">\n'
                '          <div class="brand-image-wrap"><img id="reseller-brand-image" src="" alt="" class="brand-card-image"></div>\n'
                '          <div class="brand-hero-text">\n'
                '            <h2 id="reseller-brand-name"></h2>\n'
                '            <p id="reseller-brand-stock" class="muted"></p>\n'
                '          </div>\n'
                '        </div>\n'
                '        <div class="select-wrap">\n'
                '          <select id="reseller-tier-select" aria-label="Gift card amount"></select>\n'
                '        </div>\n'
                '        <div class="select-wrap">\n'
                '          <select id="reseller-qty-select" aria-label="Quantity"></select>\n'
                '        </div>\n'
                '        <div id="reseller-tier-summary" class="tier-summary"></div>\n'
                '        <button type="button" id="reseller-grab-btn" class="buy-btn">\n'
                '          <span class="buy-btn-label">Grab from credit</span>\n'
                '          <span class="buy-btn-sub">Instant Telegram delivery</span>\n'
                '        </button>\n'
                '        <p id="reseller-grab-msg" class="muted"></p>\n'
                '      </section>\n'
                '      <button type="button" id="reseller-view-back" class="secondary">← Back to shop</button>\n'
                '    </section>\n\n'
                '    <section id="help-view" class="hidden help-panel">',
            ),
        ],
    )

    # --- miniapp style.css ---
    append_if_missing(
        SHOP / "static/miniapp/style.css",
        ".reseller-panel",
        '''
.reseller-panel {
  padding: 0 16px 32px;
}

.reseller-header {
  margin: 8px 4px 16px;
}

.reseller-header h2 {
  margin: 0 0 4px;
  font-size: 1.35rem;
}

.reseller-account {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.reseller-account .credit-line {
  font-size: 1.25rem;
  font-weight: 800;
  margin: 0 0 4px;
}

.reseller-grab-box {
  margin-top: 12px;
}

.nav-item.hidden {
  display: none;
}
''',
    )

    # --- miniapp app.js ---
    patch_file(
        SHOP / "static/miniapp/app.js",
        [
            (
                "  orderPanel.classList.add(\"hidden\");\n}",
                "  orderPanel.classList.add(\"hidden\");\n  document.getElementById(\"reseller-view\")?.classList.add(\"hidden\");\n}",
            ),
        ],
        required=False,
    )
    reseller_js = (PATCHES / "reseller_miniapp.js").read_text(encoding="utf-8")
    append_if_missing(SHOP / "static/miniapp/app.js", "let resellerProfile", reseller_js)

    # --- admin.html ---
    patch_file(
        SHOP / "templates/admin.html",
        [
            (
                '    <section>\n      <div class="grid">\n        <input id="brand" placeholder="Brand (e.g. Five Below)">',
                '    <section>\n      <h2>Resellers</h2>\n'
                '      <p class="muted">Resellers grab from all brands on credit at a custom % of face value. Cracker Barrel, Five Below, and Firehouse Subs are capped at $50 face.</p>\n'
                '      <div class="grid">\n'
                '        <input id="reseller-name" placeholder="Name">\n'
                '        <input id="reseller-telegram-id" placeholder="Telegram user ID">\n'
                '        <input id="reseller-pricing" type="number" step="0.1" placeholder="Pricing % (e.g. 17.5)">\n'
                '        <input id="reseller-credit" type="number" step="0.01" placeholder="Credit balance ($)">\n'
                '      </div>\n'
                '      <button onclick="addReseller()">Add reseller</button>\n'
                '      <p id="reseller-add-msg" class="muted"></p>\n'
                '      <button onclick="loadResellers()">Refresh resellers</button>\n'
                '      <table>\n'
                '        <thead><tr><th>Name</th><th>Telegram ID</th><th>Rate</th><th>Credit</th><th>Active</th><th>Actions</th></tr></thead>\n'
                '        <tbody id="resellers-body"></tbody>\n'
                '      </table>\n'
                '    </section>\n\n'
                '    <section>\n      <div class="grid">\n        <input id="brand" placeholder="Brand (e.g. Five Below)">',
            ),
            (
                '    loadInventory();\n    loadOrders();\n    loadSources();\n    loadCheckers();',
                '    loadInventory();\n    loadOrders();\n    loadSources();\n    loadCheckers();\n    loadResellers();',
            ),
        ],
    )

    admin_js = (PATCHES / "reseller_admin.js").read_text(encoding="utf-8")
    append_if_missing(SHOP / "templates/admin.html", "async function loadResellers", admin_js)

    # Init DB schema + seed
    subprocess.run(
        [str(SHOP / "venv/bin/python"), "-c", "import db; db.init_db(); print('db ok')"],
        check=True,
        cwd=SHOP,
    )

    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("restarted giftcard-shop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
