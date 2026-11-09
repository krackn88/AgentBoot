    async function loadResellerOrders() {
      const res = await adminFetch("/api/admin/reseller-orders?limit=200");
      const data = await res.json();
      document.getElementById("reseller-orders-body").innerHTML = (data.orders || []).map((o) => {
        const qty = Number(o.quantity || 1);
        const product = o.brand + " $" + Number(o.denomination).toFixed(2) + (qty > 1 ? " × " + qty : "");
        const who = o.reseller_name || o.telegram_first_name || o.telegram_user_id;
        return "<tr><td>#" + o.id + "</td><td>" + fmtTime(o.created_at) + "</td><td>" + who + "<br><span class=\"muted\">" + o.telegram_user_id + "</span></td><td>" + product + "</td><td>$" + Number(o.price).toFixed(2) + "</td><td>" + o.status + "</td></tr>";
      }).join("") || '<tr><td colspan="6" class="muted">No reseller orders yet.</td></tr>';
    }

