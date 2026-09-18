const authToken = document.querySelector('meta[name="auth-token"]')?.content || '';

let eventSource = null;
let knownHitIds = new Set();

function headers() {
  const h = { 'Content-Type': 'application/json' };
  if (authToken) h['X-Auth-Token'] = authToken;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { ...headers(), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

const els = {
  statusPill: document.getElementById('statusPill'),
  statTotal: document.getElementById('statTotal'),
  statChecked: document.getElementById('statChecked'),
  statHits: document.getElementById('statHits'),
  statFails: document.getElementById('statFails'),
  statCpm: document.getElementById('statCpm'),
  statCombos: document.getElementById('statCombos'),
  comboInput: document.getElementById('comboInput'),
  proxyInput: document.getElementById('proxyInput'),
  comboCount: document.getElementById('comboCount'),
  proxyCount: document.getElementById('proxyCount'),
  threads: document.getElementById('threads'),
  threadVal: document.getElementById('threadVal'),
  hitsList: document.getElementById('hitsList'),
  logBox: document.getElementById('logBox'),
};

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function updateStats(stats, comboCount) {
  els.statTotal.textContent = stats.total;
  els.statChecked.textContent = stats.checked;
  els.statHits.textContent = stats.hits;
  els.statFails.textContent = stats.fails;
  els.statCpm.textContent = stats.cpm;
  if (comboCount !== undefined) els.statCombos.textContent = comboCount;
}

function appendLog(msg) {
  const current = els.logBox.textContent;
  if (current && current.endsWith(msg + '\n')) return;
  els.logBox.textContent = current ? current + msg + '\n' : msg + '\n';
  els.logBox.scrollTop = els.logBox.scrollHeight;
}

function hitCardHtml(hit) {
  const balance = hit.gift_card_balance > 0
    ? ` • GC $${Number(hit.gift_card_balance).toFixed(2)}`
    : '';
  const rewards = (hit.rewards || []).map((r) => `↳ ${escapeHtml(r.name || '')}`).join('<br>');
  return `
    <article class="hit-card" data-id="${escapeHtml(hit.id)}">
      <h3>🌴 HIT — ${escapeHtml(hit.name || hit.email)}</h3>
      <div class="combo">${escapeHtml(hit.combo)}</div>
      <div class="meta">
        Points: ${hit.points ?? 0} • Gift Cards: ${hit.gift_cards ?? 0}${balance}
        • Rewards: ${(hit.rewards || []).length}
        ${hit.referral_code ? ` • Ref: ${escapeHtml(hit.referral_code)}` : ''}
      </div>
      ${rewards ? `<div class="rewards">${rewards}</div>` : ''}
      <div class="actions">
        <button class="btn pink small" data-action="copy" data-text="${escapeHtml(hit.line)}">Copy Hit</button>
        <button class="btn mint small" data-action="copy" data-text="${escapeHtml(hit.combo)}">Copy Combo</button>
        <button class="btn red small" data-action="delete" data-id="${escapeHtml(hit.id)}">Delete</button>
      </div>
    </article>
  `;
}

function clearHitsEmptyState() {
  const empty = els.hitsList.querySelector('.empty');
  if (empty) empty.remove();
}

function prependHit(hit) {
  if (!hit?.id || knownHitIds.has(hit.id)) return;
  knownHitIds.add(hit.id);
  clearHitsEmptyState();
  els.hitsList.insertAdjacentHTML('afterbegin', hitCardHtml(hit));
}

function renderHits(hits) {
  knownHitIds = new Set();
  if (!hits.length) {
    els.hitsList.innerHTML = '<div class="empty">No hits yet — load combos and start checking</div>';
    return;
  }
  els.hitsList.innerHTML = hits.map((hit) => {
    knownHitIds.add(hit.id);
    return hitCardHtml(hit);
  }).join('');
}

window.copyText = (text) => navigator.clipboard.writeText(text);

async function deleteHit(id) {
  await api(`/api/hits/${id}`, { method: 'DELETE' });
  knownHitIds.delete(id);
  const card = document.querySelector(`[data-id="${id}"]`);
  if (card) card.remove();
  if (!els.hitsList.querySelector('.hit-card')) {
    els.hitsList.innerHTML = '<div class="empty">No hits yet — load combos and start checking</div>';
  }
}

els.hitsList.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const action = btn.dataset.action;
  if (action === 'copy') copyText(btn.dataset.text);
  if (action === 'delete') deleteHit(btn.dataset.id);
});

async function refreshState() {
  const data = await api('/api/state');
  updateStats(data.stats, data.combo_count);
  els.comboCount.textContent = `${data.combo_count} combos loaded`;
  els.proxyCount.textContent = `${data.proxy_count} proxies loaded`;
  renderHits(data.hits);
  els.logBox.textContent = data.logs.length ? data.logs.join('\n') + '\n' : '';
  setRunning(data.running);
}

function setRunning(running) {
  els.statusPill.textContent = running ? 'Running' : 'Idle';
  els.statusPill.classList.toggle('running', running);
  document.getElementById('startBtn').disabled = running;
  document.getElementById('stopBtn').disabled = !running;
}

function connectEvents() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  const url = authToken ? `/api/events?token=${encodeURIComponent(authToken)}` : '/api/events';
  eventSource = new EventSource(url);

  eventSource.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'log') appendLog(data.message);
    if (data.type === 'stats') updateStats(data.stats);
    if (data.type === 'hit' && data.hit) {
      prependHit(data.hit);
      if (data.stats) updateStats(data.stats);
    }
    if (data.type === 'done' || data.type === 'stopped') {
      setRunning(false);
      refreshState().catch(() => {});
    }
  };

  eventSource.onerror = () => {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    setTimeout(connectEvents, 5000);
  };
}

els.threads.addEventListener('input', () => {
  els.threadVal.textContent = els.threads.value;
});

document.getElementById('loadCombos').onclick = async () => {
  const data = await api('/api/combos', { method: 'POST', body: JSON.stringify({ text: els.comboInput.value }) });
  els.comboCount.textContent = `${data.combo_count} combos loaded`;
  refreshState();
};

document.getElementById('saveCombos').onclick = () => document.getElementById('loadCombos').click();

document.getElementById('loadProxies').onclick = async () => {
  const data = await api('/api/proxies', { method: 'POST', body: JSON.stringify({ text: els.proxyInput.value }) });
  els.proxyCount.textContent = `${data.proxy_count} proxies loaded`;
};

document.getElementById('saveProxies').onclick = () => document.getElementById('loadProxies').click();

document.getElementById('startBtn').onclick = async () => {
  try {
    await api('/api/start', { method: 'POST', body: JSON.stringify({ threads: Number(els.threads.value) }) });
    setRunning(true);
  } catch (e) { alert(e.message); }
};

document.getElementById('stopBtn').onclick = async () => {
  try {
    const res = await api('/api/stop', { method: 'POST' });
    if (res.stopped) setRunning(false);
  } catch (e) {
    alert(e.message);
  }
};

document.getElementById('smokeBtn').onclick = async () => {
  const btn = document.getElementById('smokeBtn');
  btn.disabled = true;
  try {
    const res = await api('/api/smoke', { method: 'POST' });
    if (!res.ok) alert('Smoke test failed — see activity log');
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
  }
};

document.getElementById('clearHits').onclick = async () => {
  if (confirm('Clear all hits?')) {
    await api('/api/hits', { method: 'DELETE' });
    refreshState();
  }
};

document.getElementById('copyAllHits').onclick = async () => {
  const data = await api('/api/state');
  const lines = data.hits.map((h) => h.line).join('\n');
  if (lines) copyText(lines);
};

document.getElementById('clearLog').onclick = () => { els.logBox.textContent = ''; };

refreshState().catch((e) => {
  els.logBox.textContent = `Failed to load state: ${e.message}\n`;
});
connectEvents();
