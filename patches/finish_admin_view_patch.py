#!/usr/bin/env python3
from pathlib import Path

SHOP = Path("/opt/giftcard-shop")
PATCHES = SHOP / "patches"

index = SHOP / "static/miniapp/index.html"
html = index.read_text(encoding="utf-8")
if "reseller-admin-overview" not in html:
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
    print("index ok")

css = SHOP / "static/miniapp/style.css"
block = """
.reseller-admin-overview { margin-bottom: 16px; }
.reseller-admin-section h3 { margin: 0 0 10px; font-size: 1rem; }
.reseller-admin-grid { display: grid; gap: 10px; margin-bottom: 18px; }
.reseller-admin-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.reseller-admin-card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.reseller-pill { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; padding: 2px 6px; border-radius: 999px; }
.reseller-pill.ok { background: #d4edda; color: #155724; }
.reseller-pill.bad { background: #f8d7da; color: #721c24; }
.reseller-orders-list { display: grid; gap: 10px; }
.reseller-order-row { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; font-size: 0.9rem; }
"""
css_text = css.read_text(encoding="utf-8")
if ".reseller-admin-overview" not in css_text:
    css.write_text(css_text.rstrip() + block, encoding="utf-8")
    print("css ok")

admin = SHOP / "templates/admin.html"
t = admin.read_text(encoding="utf-8")
if "reseller-orders-body" not in t:
    t = t.replace(
        '        <tbody id="resellers-body"></tbody>\n      </table>\n    </section>',
        '        <tbody id="resellers-body"></tbody>\n      </table>\n'
        '      <h3 style="margin-top:20px">Reseller orders</h3>\n'
        '      <button onclick="loadResellerOrders()">Refresh orders</button>\n'
        '      <table>\n'
        '        <thead><tr><th>ID</th><th>When</th><th>Reseller</th><th>Product</th><th>Charged</th><th>Status</th></tr></thead>\n'
        '        <tbody id="reseller-orders-body"></tbody>\n'
        '      </table>\n'
        '    </section>',
    )
    t = t.replace("    loadResellers();", "    loadResellers();\n    loadResellerOrders();")
    admin_js = (PATCHES / "reseller_admin_orders.js").read_text(encoding="utf-8")
    t = t.replace("    async function toggleReseller(id, active) {", admin_js + "\n    async function toggleReseller(id, active) {")
    admin.write_text(t, encoding="utf-8")
    print("admin ok")

app_js = SHOP / "static/miniapp/app.js"
text = app_js.read_text(encoding="utf-8")
start = text.find("// --- Reseller tab (appended) ---")
app_js.write_text(text[:start] + (PATCHES / "reseller_miniapp.js").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
print("js ok")
