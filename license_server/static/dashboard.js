const token = document.querySelector('meta[name="admin-token"]')?.content || '';

function headers() {
  const h = { 'Content-Type': 'application/json' };
  if (token) h['X-Admin-Token'] = token;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function fmtTime(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString();
}

function fmtDate(ts) {
  if (!ts) return 'Never';
  return new Date(ts * 1000).toLocaleDateString();
}

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function shortHwid(hwid) {
  if (!hwid) return '—';
  const s = hwid.replace(/-/g, '');
  return s.slice(0, 8) + '…';
}

async function loadStats() {
  const s = await api('/admin/api/stats');
  document.getElementById('statsBar').innerHTML = [
    ['Total', s.total],
    ['Locked', s.locked],
    ['Active', s.active],
    ['Pending', s.pending],
    ['Expiring (7d)', s.expiring_soon],
    ['Expired', s.expired],
    ['Revoked', s.revoked],
  ].map(([label, val]) => `
    <div class="stat"><span>${label}</span><strong>${val}</strong></div>
  `).join('');
}

async function loadLicenses() {
  const { licenses } = await api('/admin/api/licenses');
  const tbody = document.getElementById('licenseRows');
  tbody.innerHTML = licenses.map((lic) => `
    <tr>
      <td>${escapeHtml(lic.customer_name)}<br><small>${escapeHtml(lic.email || '')}</small></td>
      <td class="mono">${escapeHtml(lic.activation_code)}</td>
      <td>${badge(lic.status)}</td>
      <td class="mono">${shortHwid(lic.hardware_id)}</td>
      <td>${fmtDate(lic.expires_at)}</td>
      <td>${fmtTime(lic.last_seen_at)}</td>
      <td class="actions">
        <button class="btn ghost small" data-copy="${escapeHtml(lic.activation_code)}">Copy code</button>
        <button class="btn ghost small" data-extend="${lic.id}">+30d</button>
        <button class="btn ghost small" data-reset="${lic.id}">Reset PC</button>
        <button class="btn red small" data-revoke="${lic.id}">Revoke</button>
      </td>
    </tr>
  `).join('');
}

async function loadLog() {
  const { log } = await api('/admin/api/log');
  document.getElementById('logRows').innerHTML = log.map((row) => `
    <tr>
      <td>${fmtTime(row.created_at)}</td>
      <td>${escapeHtml(row.customer_name || '—')}</td>
      <td class="mono">${escapeHtml(row.activation_code || '—')}</td>
      <td class="mono">${shortHwid(row.hardware_id)}</td>
      <td>${escapeHtml(row.ip || '')}</td>
      <td>${row.success ? '✅' : '❌'} ${escapeHtml(row.message || '')}</td>
    </tr>
  `).join('');
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function refreshAll() {
  await Promise.all([loadStats(), loadLicenses(), loadLog()]);
}

document.getElementById('refreshBtn').onclick = () => refreshAll().catch(alert);

document.getElementById('createForm').onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {
    customer_name: fd.get('customer_name'),
    hardware_id: fd.get('hardware_id'),
    email: fd.get('email'),
    days: Number(fd.get('days') || 0),
    notes: fd.get('notes'),
  };
  try {
    const res = await api('/admin/api/licenses', { method: 'POST', body: JSON.stringify(body) });
    const lic = res.license;
    document.getElementById('createResult').textContent =
      `Created code ${lic.activation_code} for ${lic.customer_name}`;
    e.target.reset();
    await refreshAll();
  } catch (err) {
    alert(err.message);
  }
};

document.getElementById('licenseRows').addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  if (btn.dataset.copy) {
    navigator.clipboard.writeText(btn.dataset.copy);
    return;
  }
  const id = btn.dataset.revoke || btn.dataset.reset || btn.dataset.extend;
  if (!id) return;
  let action, body = {};
  if (btn.dataset.revoke) {
    if (!confirm('Revoke this license?')) return;
    action = 'revoke';
  } else if (btn.dataset.reset) {
    if (!confirm('Reset hardware lock? Customer can activate on a new PC.')) return;
    action = 'reset_hwid';
  } else {
    action = 'extend';
    body = { days: 30 };
  }
  try {
    await api(`/admin/api/licenses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ action, ...body }),
    });
    await refreshAll();
  } catch (err) {
    alert(err.message);
  }
});

refreshAll().catch((e) => {
  document.body.insertAdjacentHTML('afterbegin',
    `<div style="background:#ff5252;color:#fff;padding:12px">Dashboard error: ${e.message}. Check admin token.</div>`);
});
