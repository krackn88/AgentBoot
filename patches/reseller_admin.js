
    async function loadResellers() {
      const res = await adminFetch("/api/admin/resellers");
      const data = await res.json();
      document.getElementById("resellers-body").innerHTML = (data.resellers || []).map((r) => `
        <tr>
          <td>${r.name}</td>
          <td>${r.telegram_user_id}</td>
          <td>${r.pricing_label}</td>
          <td>$${Number(r.credit_balance).toFixed(2)}</td>
          <td>${r.active ? '<span class="ok">yes</span>' : '<span class="bad">no</span>'}</td>
          <td class="actions">
            <button onclick="editResellerCredit(${r.id}, ${Number(r.credit_balance).toFixed(2)})">Set credit</button>
            <button onclick="toggleReseller(${r.id}, ${r.active ? 'false' : 'true'})">${r.active ? 'Deactivate' : 'Activate'}</button>
          </td>
        </tr>`).join("") || '<tr><td colspan="6" class="muted">No resellers yet.</td></tr>';
    }

    async function addReseller() {
      let pct = Number(document.getElementById("reseller-pricing").value);
      if (pct > 1) pct = pct / 100;
      const body = {
        name: document.getElementById("reseller-name").value,
        telegram_user_id: Number(document.getElementById("reseller-telegram-id").value),
        pricing_percentage: pct,
        credit_balance: Number(document.getElementById("reseller-credit").value || 0),
      };
      const res = await adminFetch("/api/admin/resellers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      document.getElementById("reseller-add-msg").textContent = data.ok
        ? `Added ${body.name}`
        : (data.error || "Failed");
      if (data.ok) loadResellers();
    }

    async function editResellerCredit(id, current) {
      const val = prompt("New credit balance ($)", String(current));
      if (val === null) return;
      const res = await adminFetch(`/api/admin/resellers/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credit_balance: Number(val) }),
      });
      const data = await res.json();
      if (data.ok) loadResellers(); else alert(data.error || "Failed");
    }

    async function toggleReseller(id, active) {
      const res = await adminFetch(`/api/admin/resellers/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: active === true || active === "true" }),
      });
      const data = await res.json();
      if (data.ok) loadResellers(); else alert(data.error || "Failed");
    }
