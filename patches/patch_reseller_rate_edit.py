#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

SHOP = Path("/opt/giftcard-shop")
PATCHES = SHOP / "patches"


def patch_app() -> None:
    app = SHOP / "app.py"
    text = app.read_text(encoding="utf-8")
    if "/api/reseller/admin/resellers" in text:
        print("app route exists")
        return

    helper = '''

def _reseller_update_fields(data: dict) -> dict:
    fields: dict = {}
    for key in ("name", "telegram_user_id", "credit_balance", "credit_limit", "notes", "active"):
        if key in data:
            fields[key] = data[key]
    if "pricing_percentage" in data:
        pct = float(data["pricing_percentage"])
        if pct > 1:
            pct = pct / 100.0
        fields["pricing_percentage"] = pct
    return fields

'''
    anchor = "\n@app.put(\"/api/admin/resellers/<int:reseller_id>\")"
    if "def _reseller_update_fields" not in text:
        text = text.replace(anchor, helper + anchor, 1)

    text = text.replace(
        '''@app.put("/api/admin/resellers/<int:reseller_id>")
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
    return jsonify({"ok": True, "reseller": row})''',
        '''@app.put("/api/admin/resellers/<int:reseller_id>")
def admin_update_reseller(reseller_id: int):
    if not _admin_ok():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    fields = _reseller_update_fields(data)
    try:
        row = db.update_reseller(reseller_id, **fields)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not row:
        return jsonify({"ok": False, "error": "Reseller not found"}), 404
    return jsonify({"ok": True, "reseller": row})


@app.put("/api/reseller/admin/resellers/<int:reseller_id>")
def miniapp_admin_update_reseller(reseller_id: int):
    try:
        user = _telegram_user_from_request()
    except TelegramAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    user_id = user.get("id")
    if not user_id or not _is_admin_telegram_user(int(user_id)):
        return jsonify({"ok": False, "error": "Admin only"}), 403
    data = request.get_json(force=True, silent=True) or {}
    fields = _reseller_update_fields(data)
    if not fields:
        return jsonify({"ok": False, "error": "No fields to update"}), 400
    try:
        row = db.update_reseller(reseller_id, **fields)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not row:
        return jsonify({"ok": False, "error": "Reseller not found"}), 404
    return jsonify(
        {
            "ok": True,
            "reseller": resellers.serialize_reseller_row(row),
            "admin_overview": resellers.admin_overview(),
        }
    )''',
        1,
    )
    app.write_text(text, encoding="utf-8")
    print("patched app.py")


def replace_miniapp_js() -> None:
    app_js = SHOP / "static/miniapp/app.js"
    text = app_js.read_text(encoding="utf-8")
    start = text.find("// --- Reseller tab (appended) ---")
    app_js.write_text(text[:start] + (PATCHES / "reseller_miniapp.js").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    print("updated miniapp js")


def patch_css() -> None:
    css = SHOP / "static/miniapp/style.css"
    block = """
.reseller-rate-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.reseller-rate-edit label {
  font-size: 0.8rem;
  color: var(--muted, #888);
}

.reseller-rate-input {
  width: 88px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: inherit;
}

.reseller-rate-save {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--accent);
  font-weight: 700;
  cursor: pointer;
}

.reseller-rate-msg {
  margin: 6px 0 0;
  min-height: 1rem;
}
"""
    text = css.read_text(encoding="utf-8")
    if ".reseller-rate-edit" not in text:
        css.write_text(text.rstrip() + block, encoding="utf-8")
        print("patched css")


def patch_admin_html() -> None:
    admin = SHOP / "templates/admin.html"
    text = admin.read_text(encoding="utf-8")
    if "editResellerRate" in text:
        print("admin html ok")
        return
    text = text.replace(
        '<button onclick="editResellerCredit(${r.id}, ${Number(r.credit_balance).toFixed(2)})">Set credit</button>',
        '<button onclick="editResellerRate(${r.id}, ${(Number(r.pricing_percentage) * 100).toFixed(1)})">Set rate</button>\n'
        '            <button onclick="editResellerCredit(${r.id}, ${Number(r.credit_balance).toFixed(2)})">Set credit</button>',
    )
    insert = '''    async function editResellerRate(id, current) {
      const val = prompt("New pricing rate (% of face value)", String(current));
      if (val === null) return;
      const res = await adminFetch(`/api/admin/resellers/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pricing_percentage: Number(val) }),
      });
      const data = await res.json();
      if (data.ok) loadResellers(); else alert(data.error || "Failed");
    }

'''
    text = text.replace("    async function editResellerCredit(id, current) {", insert + "    async function editResellerCredit(id, current) {")
    admin.write_text(text, encoding="utf-8")
    print("patched admin.html")


def main() -> None:
    patch_app()
    replace_miniapp_js()
    patch_css()
    patch_admin_html()
    subprocess.run(["systemctl", "restart", "giftcard-shop"], check=True)
    print("done")


if __name__ == "__main__":
    main()
