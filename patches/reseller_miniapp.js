
// --- Reseller tab (appended) ---
let resellerProfile = null;
let resellerIsAdmin = false;
let resellerAdminOverview = null;
let resellerBrands = [];
let resellerCurrentBrand = null;
let resellerCurrentTiers = [];
let resellerGrabbing = false;

const resellerView = document.getElementById("reseller-view");
const navReseller = document.getElementById("nav-reseller");
const resellerAccount = document.getElementById("reseller-account");
const resellerAdminOverviewEl = document.getElementById("reseller-admin-overview");
const resellerGrabSection = document.getElementById("reseller-grab-section");
const resellerBrandsEl = document.getElementById("reseller-brands");
const resellerGrabPanel = document.getElementById("reseller-grab-panel");
const resellerTierSelect = document.getElementById("reseller-tier-select");
const resellerQtySelect = document.getElementById("reseller-qty-select");
const resellerTierSummary = document.getElementById("reseller-tier-summary");
const resellerGrabBtn = document.getElementById("reseller-grab-btn");
const resellerGrabMsg = document.getElementById("reseller-grab-msg");
const resellerHeaderTitle = document.getElementById("reseller-header-title");
const resellerHeaderSub = document.getElementById("reseller-header-sub");

function resellerRate() {
  return Number(resellerProfile?.pricing_percentage) || 0;
}

function resellerChargeFor(tier, qty) {
  const face = Number(tier) || 0;
  const q = Math.max(1, Number(qty) || 1);
  return Math.round(face * resellerRate() * q * 100) / 100;
}

function fmtResellerTime(ts) {
  if (!ts) return "—";
  return new Date(Number(ts) * 1000).toLocaleString();
}

function updateResellerNavVisibility() {
  if (!navReseller) return;
  navReseller.classList.toggle("hidden", !resellerProfile && !resellerIsAdmin);
  const label = navReseller.querySelector("span");
  if (label) label.textContent = resellerIsAdmin && !resellerProfile ? "Resellers" : "Reseller";
}

function renderResellerAdminOverview() {
  if (!resellerAdminOverviewEl) return;
  const overview = resellerAdminOverview;
  if (!resellerIsAdmin || !overview) {
    resellerAdminOverviewEl.classList.add("hidden");
    return;
  }
  resellerAdminOverviewEl.classList.remove("hidden");
  const resellers = overview.resellers || [];
  const orders = overview.orders || [];
  const resellerRows = resellers
    .map((r) => {
      const active = r.active
        ? '<span class="reseller-pill ok">active</span>'
        : '<span class="reseller-pill bad">off</span>';
      const ratePct = (Number(r.pricing_percentage) * 100).toFixed(1);
      return `
        <div class="reseller-admin-card">
          <div class="reseller-admin-card-top">
            <strong>${escapeHtml(r.name)}</strong> ${active}
          </div>
          <div class="muted">TG ${r.telegram_user_id}</div>
          <div class="credit-line">$${Number(r.credit_balance).toFixed(2)} credit</div>
          <div class="reseller-rate-edit">
            <label for="reseller-rate-${r.id}">Rate %</label>
            <input id="reseller-rate-${r.id}" type="number" step="0.1" min="0.1" class="reseller-rate-input" data-reseller-id="${r.id}" value="${ratePct}">
            <button type="button" class="reseller-rate-save" data-save-rate="${r.id}">Save</button>
          </div>
          <p class="reseller-rate-msg muted" data-rate-msg="${r.id}"></p>
        </div>`;
    })
    .join("") || "<p class='muted'>No resellers configured.</p>";

  const orderRows = orders.length
    ? orders
        .map((o) => {
          const who = o.reseller_name || o.telegram_first_name || `TG ${o.telegram_user_id}`;
          const qty = Number(o.quantity || 1);
          const product = `${escapeHtml(o.brand)} $${Number(o.denomination).toFixed(2)}${qty > 1 ? ` × ${qty}` : ""}`;
          return `
            <div class="reseller-order-row">
              <div><strong>#${o.id}</strong> · ${escapeHtml(who)}</div>
              <div>${product}</div>
              <div class="muted">$${Number(o.price).toFixed(2)} · ${escapeHtml(o.status || "")} · ${fmtResellerTime(o.created_at)}</div>
            </div>`;
        })
        .join("")
    : "<p class='muted'>No reseller orders yet.</p>";

  resellerAdminOverviewEl.innerHTML = `
    <div class="reseller-admin-section">
      <h3>All resellers</h3>
      <div class="reseller-admin-grid">${resellerRows}</div>
    </div>
    <div class="reseller-admin-section">
      <h3>Reseller orders</h3>
      <div class="reseller-orders-list">${orderRows}</div>
    </div>
  `;

  resellerAdminOverviewEl.querySelectorAll("[data-save-rate]").forEach((btn) => {
    btn.addEventListener("click", () => saveResellerRate(btn.dataset.saveRate));
  });
}

async function saveResellerRate(resellerId) {
  const id = String(resellerId);
  const input = resellerAdminOverviewEl?.querySelector(`input[data-reseller-id="${id}"]`);
  const msg = resellerAdminOverviewEl?.querySelector(`[data-rate-msg="${id}"]`);
  if (!input) return;
  const pct = Number(input.value);
  if (!pct || pct <= 0) {
    if (msg) msg.textContent = "Enter a valid rate %";
    return;
  }
  if (msg) msg.textContent = "Saving…";
  try {
    const res = await fetch(apiUrl(`/api/reseller/admin/resellers/${id}`), {
      method: "PUT",
      headers: { ...apiHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ pricing_percentage: pct }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Failed to save rate");
    resellerAdminOverview = data.admin_overview || resellerAdminOverview;
    if (msg) msg.textContent = `Saved at ${pct}%`;
    renderResellerAdminOverview();
  } catch (err) {
    if (msg) msg.textContent = err.message || "Could not save rate";
  }
}

function renderResellerAccount() {
  if (!resellerAccount) return;
  if (!resellerProfile) {
    resellerAccount.classList.add("hidden");
    resellerAccount.innerHTML = "";
    return;
  }
  resellerAccount.classList.remove("hidden");
  const pct = (resellerRate() * 100).toFixed(1);
  const credit = Number(resellerProfile.credit_balance || 0).toFixed(2);
  resellerAccount.innerHTML = `
    <p class="credit-line">$${credit} credit</p>
    <p class="muted">${escapeHtml(resellerProfile.name || "Reseller")} · ${pct}% of face · Cracker Barrel / Five Below / Firehouse capped at $50</p>
  `;
}

function renderResellerBrands() {
  if (!resellerBrandsEl) return;
  if (!resellerBrands.length) {
    resellerBrandsEl.innerHTML = "<p class='empty'>No reseller stock right now.</p>";
    return;
  }
  resellerBrandsEl.innerHTML = resellerBrands
    .map((b) => `
        <button type="button" class="store-card" data-reseller-brand="${escapeHtml(b.brand)}">
          <div class="store-card-art"><img src="${escapeHtml(cardArtUrl(b))}" alt="${escapeHtml(b.brand)}"></div>
          <div class="store-card-body">
            <div class="store-card-title">${escapeHtml(b.brand)}</div>
            <div class="store-card-meta">${b.stock || 0} in stock · ${b.tier_count || 0} tiers</div>
          </div>
        </button>`)
    .join("");

  resellerBrandsEl.querySelectorAll("[data-reseller-brand]").forEach((btn) => {
    btn.addEventListener("click", () => openResellerBrand(btn.dataset.resellerBrand));
  });
}

function openResellerBrand(brandName) {
  resellerCurrentBrand = resellerBrands.find((b) => b.brand === brandName);
  if (!resellerCurrentBrand) return;
  resellerCurrentTiers = resellerCurrentBrand.tiers || [];
  resellerBrandsEl.classList.add("hidden");
  resellerGrabPanel.classList.remove("hidden");
  const img = document.getElementById("reseller-brand-image");
  const nameEl = document.getElementById("reseller-brand-name");
  const stockEl = document.getElementById("reseller-brand-stock");
  if (img) {
    img.src = cardArtUrl(resellerCurrentBrand);
    img.alt = resellerCurrentBrand.brand;
  }
  if (nameEl) nameEl.textContent = resellerCurrentBrand.brand;
  if (stockEl) {
    stockEl.textContent = `${resellerCurrentBrand.stock || 0} cards available · your rate ${(resellerRate() * 100).toFixed(1)}%`;
  }
  resellerTierSelect.innerHTML = resellerCurrentTiers
    .map((t) => `<option value="${t.tier}">${escapeHtml(t.label)} · ${t.stock} in stock</option>`)
    .join("");
  syncResellerQty();
  updateResellerSummary();
}

function syncResellerQty() {
  const tier = resellerCurrentTiers.find((t) => String(t.tier) === String(resellerTierSelect.value));
  const maxStock = tier ? Number(tier.stock) || 1 : 1;
  const maxQty = Math.max(1, Math.min(MAX_ORDER_QTY, maxStock));
  const prev = Number(resellerQtySelect.value) || 1;
  resellerQtySelect.innerHTML = Array.from({ length: maxQty }, (_, i) => {
    const n = i + 1;
    return `<option value="${n}">${n}</option>`;
  }).join("");
  resellerQtySelect.value = String(Math.min(Math.max(prev, 1), maxQty));
}

function updateResellerSummary() {
  const tier = Number(resellerTierSelect.value) || 0;
  const qty = Number(resellerQtySelect.value) || 1;
  const charge = resellerChargeFor(tier, qty);
  const faceTotal = tier * qty;
  const credit = Number(resellerProfile?.credit_balance || 0);
  const ok = charge <= credit;
  resellerTierSummary.innerHTML = `
    Face $${faceTotal.toFixed(2)} · your cost <strong>$${charge.toFixed(2)}</strong>
    <br><span class="muted">${ok ? "Delivered instantly to this chat" : "Not enough credit for this grab"}</span>
  `;
  resellerGrabBtn.disabled = !ok || resellerGrabbing;
}

function updateResellerLayout() {
  if (resellerHeaderTitle) {
    resellerHeaderTitle.textContent = resellerIsAdmin && !resellerProfile
      ? "Reseller admin"
      : resellerIsAdmin
        ? "Reseller admin & grabs"
        : "Reseller grabs";
  }
  if (resellerHeaderSub) {
    resellerHeaderSub.textContent = resellerIsAdmin
      ? "View all reseller credit and orders below"
      : "All brands · Cracker Barrel / Five Below / Firehouse capped at $50";
  }
  renderResellerAdminOverview();
  if (resellerGrabSection) {
    resellerGrabSection.classList.toggle("hidden", !resellerProfile);
  }
}

async function loadResellerProfile() {
  try {
    const res = await fetch(apiUrl("/api/reseller/me"), { headers: apiHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    resellerProfile = data.reseller || null;
    resellerIsAdmin = Boolean(data.is_admin);
    resellerAdminOverview = data.admin_overview || null;
    updateResellerNavVisibility();
    updateResellerLayout();
  } catch {
    // non-fatal
  }
}

async function loadResellerCatalog() {
  if (!resellerProfile) return;
  resellerBrandsEl.innerHTML = "<p class='empty'><span class='loading-spinner'></span>Loading…</p>";
  try {
    const res = await fetch(apiUrl("/api/reseller/catalog"), { headers: apiHeaders() });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Failed");
    resellerProfile = data.reseller || resellerProfile;
    resellerBrands = data.brands || [];
    renderResellerAccount();
    renderResellerBrands();
  } catch (err) {
    resellerBrandsEl.innerHTML = `<p class='empty'>${escapeHtml(err.message || "Could not load catalog")}</p>`;
  }
}

async function refreshResellerAdminOverview() {
  if (!resellerIsAdmin) return;
  try {
    const res = await fetch(apiUrl("/api/reseller/me"), { headers: apiHeaders() });
    const data = await res.json();
    if (!data.ok) return;
    resellerAdminOverview = data.admin_overview || null;
    resellerProfile = data.reseller || resellerProfile;
    resellerIsAdmin = Boolean(data.is_admin);
    renderResellerAdminOverview();
    renderResellerAccount();
    updateResellerLayout();
  } catch {
    // non-fatal
  }
}

function closeResellerGrabPanel() {
  resellerGrabPanel?.classList.add("hidden");
  resellerBrandsEl?.classList.remove("hidden");
  resellerCurrentBrand = null;
  if (resellerGrabMsg) resellerGrabMsg.textContent = "";
}

function showResellerView() {
  hideAllViews();
  resellerView?.classList.remove("hidden");
  stepNav?.classList.add("hidden");
  setNav("reseller");
  closeResellerGrabPanel();
  updateResellerLayout();
  refreshResellerAdminOverview();
  loadResellerCatalog();
}

async function grabResellerHit() {
  if (!resellerCurrentBrand || resellerGrabbing) return;
  const tier = Number(resellerTierSelect.value) || 0;
  const qty = Number(resellerQtySelect.value) || 1;
  resellerGrabbing = true;
  resellerGrabBtn.disabled = true;
  resellerGrabMsg.textContent = "Grabbing…";
  try {
    const res = await fetch(apiUrl("/api/reseller/grab"), {
      method: "POST",
      headers: { ...apiHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        brand: resellerCurrentBrand.brand,
        tier,
        quantity: qty,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Grab failed");
    resellerProfile = data.reseller || resellerProfile;
    renderResellerAccount();
    updateResellerSummary();
    resellerGrabMsg.textContent = `Order #${data.order.id} — delivering to your chat now.`;
    await loadResellerCatalog();
    await refreshResellerAdminOverview();
    openResellerBrand(resellerCurrentBrand.brand);
  } catch (err) {
    resellerGrabMsg.textContent = err.message || "Grab failed";
  } finally {
    resellerGrabbing = false;
    updateResellerSummary();
  }
}

document.getElementById("reseller-view-back")?.addEventListener("click", showShopView);
document.getElementById("reseller-back-brands")?.addEventListener("click", closeResellerGrabPanel);
resellerTierSelect?.addEventListener("change", () => {
  syncResellerQty();
  updateResellerSummary();
});
resellerQtySelect?.addEventListener("change", updateResellerSummary);
resellerGrabBtn?.addEventListener("click", grabResellerHit);

document.querySelectorAll(".nav-item").forEach((btn) => {
  if (btn.dataset.nav === "reseller") {
    btn.addEventListener("click", () => showResellerView());
  }
});

const _hideAllViewsOrig = hideAllViews;
hideAllViews = function () {
  _hideAllViewsOrig();
  document.getElementById("reseller-view")?.classList.add("hidden");
};

loadResellerProfile();
