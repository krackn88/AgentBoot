
// --- Reseller tab (appended) ---
let resellerProfile = null;
let resellerBrands = [];
let resellerCurrentBrand = null;
let resellerCurrentTiers = [];
let resellerGrabbing = false;

const resellerView = document.getElementById("reseller-view");
const navReseller = document.getElementById("nav-reseller");
const resellerAccount = document.getElementById("reseller-account");
const resellerBrandsEl = document.getElementById("reseller-brands");
const resellerGrabPanel = document.getElementById("reseller-grab-panel");
const resellerTierSelect = document.getElementById("reseller-tier-select");
const resellerQtySelect = document.getElementById("reseller-qty-select");
const resellerTierSummary = document.getElementById("reseller-tier-summary");
const resellerGrabBtn = document.getElementById("reseller-grab-btn");
const resellerGrabMsg = document.getElementById("reseller-grab-msg");

function resellerRate() {
  return Number(resellerProfile?.pricing_percentage) || 0;
}

function resellerChargeFor(tier, qty) {
  const face = Number(tier) || 0;
  const q = Math.max(1, Number(qty) || 1);
  return Math.round(face * resellerRate() * q * 100) / 100;
}

function renderResellerAccount() {
  if (!resellerAccount || !resellerProfile) return;
  const pct = (resellerRate() * 100).toFixed(1);
  const credit = Number(resellerProfile.credit_balance || 0).toFixed(2);
  resellerAccount.innerHTML = `
    <p class="credit-line">$${credit} credit</p>
    <p class="muted">${escapeHtml(resellerProfile.name || "Reseller")} · ${pct}% of face · max $50 hits</p>
  `;
}

function renderResellerBrands() {
  if (!resellerBrandsEl) return;
  if (!resellerBrands.length) {
    resellerBrandsEl.innerHTML = "<p class='empty'>No reseller stock right now.</p>";
    return;
  }
  resellerBrandsEl.innerHTML = resellerBrands
    .map((b) => {
      const art = escapeHtml(cardArtUrl(b));
      const discount = escapeHtml(b.discount_label || "");
      return `
        <button type="button" class="store-card" data-reseller-brand="${escapeHtml(b.brand)}">
          <div class="store-card-art"><img src="${art}" alt="${escapeHtml(b.brand)}"></div>
          <div class="store-card-body">
            <div class="store-card-title">${escapeHtml(b.brand)}</div>
            <div class="store-card-meta">${b.stock || 0} in stock · ${b.tier_count || 0} tiers</div>
          </div>
        </button>`;
    })
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

async function loadResellerProfile() {
  try {
    const res = await fetch(apiUrl("/api/reseller/me"), { headers: apiHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    resellerProfile = data.reseller || null;
    if (navReseller) {
      navReseller.classList.toggle("hidden", !resellerProfile);
    }
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

function closeResellerGrabPanel() {
  resellerGrabPanel?.classList.add("hidden");
  resellerBrandsEl?.classList.remove("hidden");
  resellerCurrentBrand = null;
  resellerGrabMsg.textContent = "";
}

function showResellerView() {
  hideAllViews();
  resellerView?.classList.remove("hidden");
  stepNav?.classList.add("hidden");
  setNav("reseller");
  closeResellerGrabPanel();
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

const _origSetNav = typeof setNav === "function" ? null : null;
document.querySelectorAll(".nav-item").forEach((btn) => {
  if (btn.dataset.nav === "reseller") {
    btn.addEventListener("click", () => showResellerView());
  }
});

// Ensure reseller panel hides when switching to shop/orders/help
const _hideAllViewsOrig = hideAllViews;
hideAllViews = function () {
  _hideAllViewsOrig();
  document.getElementById("reseller-view")?.classList.add("hidden");
};

loadResellerProfile();
